"""LianaAutomation adapter: "Contact me" requests become survey_contact_request events
(POST /import with no_duplicates).

Each organisation connects its own LianaAutomation account on the Integrations page,
so the host, credentials, channel and switches come from its `integrations` row, not
from environment variables. Every request is a row in the sync log, so the admin sees
what was sent and can press Retry after fixing a broken connection.

    not connected, or "Contact me" requests switched off -> skipped (nothing to send)
    connection not tested, or no channel                  -> failed in the sync log, Retry
    TemporaryError (5xx, timeout)                         -> retrying; raised so the
                                                             connector tries again later
    other LianaError (bad data, wrong host, credentials) -> failed; raised as
                                                             DeliveryFailed (dead letter)

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
from liana_survey_shared.messages import ContactRequested

from ...automation import domain, repo, secrets
from ...automation.client import AutomationClient, LianaError, build_client
from ...automation.client import TemporaryError as LianaTemporaryError
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
    ) -> None:
        self.secret_key = secret_key
        # The demo host only in dev mode, as on the Integrations page.
        self.build = build or partial(build_client, allow_demo=allow_demo)
        self.database_url = database_url

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
                    event.contact_ref, event.survey_id, event.contact_request_id, event.created_at
                )
                logged = repo.add_event(
                    conn, event.tenant_id, domain.CONTACT_REQUEST_VERB, payload, test=False
                )
            problem = domain.not_ready(connection)
            if problem:
                repo.finish_event(conn, logged["id"], "failed", problem)
                return
        try:
            secret = secrets.decrypt(connection["secret_encrypted"], self.secret_key)
        except secrets.UnreadableSecret:
            message = "The saved secret can no longer be read. Enter the credentials again."
            self._finish(event.tenant_id, logged["id"], "failed", message, broken=True)
            raise DeliveryFailed(message) from None
        try:
            client = self.build(connection["host"], connection["client_id"], secret)
            client.import_events(domain.import_body(connection["channel_id"], [logged["payload"]]))
        except LianaTemporaryError as error:
            self._finish(event.tenant_id, logged["id"], "retrying", str(error))
            raise TemporaryError(str(error)) from error
        except LianaError as error:
            broken = error.kind in ("config", "auth")
            self._finish(event.tenant_id, logged["id"], "failed", str(error), broken=broken)
            raise DeliveryFailed(str(error)) from error
        self._finish(event.tenant_id, logged["id"], "sent", None)

    def _finish(
        self, tenant_id: UUID, event_id: UUID, status: str, error: str | None, broken=False
    ) -> None:
        """Record the attempt. A wrong host or credentials also mark the connection as
        broken, so the Integrations page shows the error."""
        with self._db(tenant_id) as conn:
            repo.finish_event(conn, event_id, status, error)
            if broken:
                repo.update(conn, status="error", last_error=error)
