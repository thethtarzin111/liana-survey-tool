"""LianaAutomation adapter: saved answers become survey_answered events and "Contact
me" requests survey_contact_request events (POST /import with no_duplicates).

Each organisation connects its own LianaAutomation account on the Integrations page,
so the host, credentials, channel and switches come from its `integrations` row, not
from environment variables. Every request is a row in the sync log, so the admin sees
what was sent and can press Retry after fixing a broken connection.

    not connected, or that switch is off                  -> nothing (no sync log row)
    an anonymous answer                                   -> "skipped" row with the reason
    LianaMailer has no such contact                       -> "skipped" row with the reason
    the email address can't be looked up now             -> failed in the sync log, Retry
    connection not tested, or no channel                  -> failed in the sync log, Retry
    TemporaryError (5xx, timeout)                         -> retrying; raised so the
                                                             connector tries again later,
                                                             failed after its last attempt
    other LianaError (bad data, wrong host, credentials) -> failed; raised as
                                                             DeliveryFailed (dead letter)

LianaAutomation matches contacts by email, so a newsletter reader's contact id is
turned into their address first (automation.contacts, LianaMailer API). Only
LianaAutomation's acceptance makes a row "sent": its answer is checked and stored
(client.import_events), for the sync log's Details.

Calls to Liana run outside the database transaction, like the Integrations API.
"""

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import partial
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from liana_survey_shared.db import tenant_connection
from liana_survey_shared.messages import AnswerRecorded, ContactRequested

from ...automation import contacts, domain, repo, secrets
from ...automation.client import AutomationClient, LianaError, build_client
from ...automation.client import TemporaryError as LianaTemporaryError
from ...ports.contact_directory import ContactDirectory
from ...ports.contact_events import TemporaryError

log = logging.getLogger(__name__)

ClientFactory = Callable[[str, str, str], AutomationClient]


class DeliveryFailed(Exception):
    """LianaAutomation refused the event for good. It stays in the sync log as failed,
    with Retry; the message is not retried automatically."""


class LianaAutomationContactEvents:
    def __init__(
        self,
        secret_key: str,
        *,
        allow_demo: bool = False,
        build: ClientFactory | None = None,
        database_url: str | None = None,
        directory: ContactDirectory | None = None,
    ) -> None:
        self.secret_key = secret_key
        # The demo host only in dev mode, as on the Integrations page.
        self.build = build or partial(build_client, allow_demo=allow_demo)
        self.database_url = database_url
        if directory is None:
            from ..lianamailer.directory import NotSetUp

            directory = NotSetUp()
        self.directory = directory

    @contextmanager
    def _db(self, tenant_id: UUID) -> Iterator[psycopg.Connection]:
        with tenant_connection(tenant_id, self.database_url) as conn:
            conn.row_factory = dict_row  # the repo reads rows by column name
            yield conn

    def send_contact_requested(self, event: ContactRequested) -> None:
        with self._db(event.tenant_id) as conn:
            connection = repo.get(conn)
            if not domain.sends_contact_requests(connection):
                log.info("contact request %s not sent: switched off", event.contact_request_id)
                return
            logged = repo.event_for_request(conn, event.contact_request_id)
            if logged is not None and logged["status"] == "sent":
                return  # a redelivered message: Liana has it already
            if logged is None:
                payload = domain.contact_request_event(
                    domain.contact_identity(event.contact_ref, event.contact_email),
                    event.survey_id,
                    event.contact_request_id,
                    event.created_at,
                )
                logged = repo.add_event(
                    conn,
                    event.tenant_id,
                    domain.CONTACT_REQUEST_VERB,
                    payload,
                    test=False,
                    response_id=event.response_id,
                )
            problem = domain.not_ready(connection)
            if problem:
                repo.finish_event(conn, logged["id"], "failed", problem)
                return
        # The address also goes on the response, for Results -> Responses.
        logged = self._with_email(event.tenant_id, logged, event.response_id)
        if logged is not None:
            self._deliver(event.tenant_id, connection, logged)

    def send_answer_recorded(self, event: AnswerRecorded) -> None:
        with self._db(event.tenant_id) as conn:
            connection = repo.get(conn)
            if not domain.sends_answers(connection):
                return
            payload, not_sent = domain.answer_event(
                event.survey_id,
                event.survey_title,
                event.main_kind,
                event.score,
                event.campaign,
                event.contact_ref,
            )
        problem = None if not_sent else domain.not_ready(connection)
        status = "skipped" if not_sent else "failed" if problem else "pending"
        reason = not_sent or problem
        if status == "pending":
            # Before the row is written, so the same answer gives the same payload
            # (with the address) and is recognised instead of sent again.
            try:
                payload = contacts.with_email(
                    payload, self.directory, lambda: self._db(event.tenant_id)
                )
            except contacts.NotSent as error:
                status, reason = "skipped", str(error)
            except contacts.LookupFailed as error:
                status, reason = "failed", str(error)
        with self._db(event.tenant_id) as conn:
            logged = repo.log_answer_event(
                conn,
                event.tenant_id,
                event.response_id,
                domain.ANSWER_VERB,
                payload,
                status,
                reason,
            )
        if logged is None or status != "pending":
            return  # nothing new to send, not sent on purpose, or waiting for Retry
        self._deliver(event.tenant_id, connection, logged)

    def give_up(self, event: AnswerRecorded | ContactRequested, reason: str) -> None:
        """The connector's last attempt failed too: the retrying row becomes failed, so
        the sync log shows Retry instead of waiting for a retry that never comes."""
        error = f"Gave up after several tries. Last error: {reason}"
        with self._db(event.tenant_id) as conn:
            if isinstance(event, ContactRequested):
                repo.give_up_event(conn, error, contact_request_id=event.contact_request_id)
            else:
                repo.give_up_event(conn, error, response_id=event.response_id)

    def _with_email(self, tenant_id: UUID, logged: dict, response_id: UUID | None) -> dict | None:
        """The row with the contact's address in its payload, or None when it must not
        be sent now (the row then says why: skipped or failed)."""
        try:
            payload = contacts.with_email(
                logged["payload"], self.directory, lambda: self._db(tenant_id), response_id
            )
        except (contacts.NotSent, contacts.LookupFailed) as error:
            status = "skipped" if isinstance(error, contacts.NotSent) else "failed"
            with self._db(tenant_id) as conn:
                repo.mark_event(conn, logged["id"], status, str(error))
            return None
        if payload is not logged["payload"]:
            with self._db(tenant_id) as conn:
                repo.set_payload(conn, logged["id"], payload)
        return {**logged, "payload": payload}

    def _deliver(self, tenant_id: UUID, connection: dict, logged: dict) -> None:
        """Send one pending sync log row and record the outcome."""
        try:
            secret = secrets.decrypt(connection["secret_encrypted"], self.secret_key)
        except secrets.UnreadableSecret:
            message = "The saved secret can no longer be read. Enter the credentials again."
            self._finish(tenant_id, logged["id"], "failed", message, broken=True)
            raise DeliveryFailed(message) from None
        try:
            client = self.build(connection["host"], connection["client_id"], secret)
            answer = client.import_events(
                domain.import_body(connection["channel_id"], [logged["payload"]])
            )
        except LianaTemporaryError as error:
            self._finish(tenant_id, logged["id"], "retrying", str(error), response=error.response)
            raise TemporaryError(str(error)) from error
        except LianaError as error:
            broken = error.kind in ("config", "auth")
            self._finish(
                tenant_id,
                logged["id"],
                "failed",
                str(error),
                broken=broken,
                response=error.response,
            )
            raise DeliveryFailed(str(error)) from error
        self._finish(tenant_id, logged["id"], "sent", None, response=answer)

    def _finish(
        self,
        tenant_id: UUID,
        event_id: UUID,
        status: str,
        error: str | None,
        broken=False,
        response: str | None = None,
    ) -> None:
        """Record the attempt and Liana's answer. A wrong host or credentials also mark
        the connection as broken, so the Integrations page shows the error."""
        with self._db(tenant_id) as conn:
            repo.finish_event(conn, event_id, status, error, response)
            if broken:
                repo.update(conn, status="error", last_error=error)
