from datetime import timedelta
from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

PROVIDER = "liana_automation"

_COLUMNS = """id, host, auth_type, client_id, secret_encrypted, secret_hint, channel_id,
              channel_name, settings, status, last_error, updated_at"""


def get(conn: psycopg.Connection) -> dict[str, Any] | None:
    """This organisation's LianaAutomation connection, or None."""
    return conn.execute(
        f"select {_COLUMNS} from integrations where provider = %s", (PROVIDER,)
    ).fetchone()


def save_credentials(
    conn: psycopg.Connection,
    tenant_id: UUID,
    host: str,
    client_id: str,
    secret_encrypted: bytes | None,
    secret_hint: str | None,
    settings: dict[str, Any],
) -> dict[str, Any]:
    """Insert or update the connection. A None secret keeps the saved one (the row must
    exist then). New credentials always need a new test, so the status goes back to
    disconnected. The channel is kept only when the host stays the same."""
    if secret_encrypted is None:
        return conn.execute(
            f"""update integrations set
                  channel_id = case when host = %(host)s then channel_id end,
                  channel_name = case when host = %(host)s then channel_name end,
                  host = %(host)s, client_id = %(client_id)s,
                  status = 'disconnected', last_error = null, updated_at = now()
                where provider = %(provider)s returning {_COLUMNS}""",
            {"host": host, "client_id": client_id, "provider": PROVIDER},
        ).fetchone()
    return conn.execute(
        f"""insert into integrations (tenant_id, provider, host, client_id, secret_encrypted,
                                      secret_hint, settings)
            values (%(tenant)s, %(provider)s, %(host)s, %(client_id)s, %(secret)s, %(hint)s,
                    %(settings)s)
            on conflict (tenant_id, provider) do update set
              host = excluded.host,
              client_id = excluded.client_id,
              secret_encrypted = excluded.secret_encrypted,
              secret_hint = excluded.secret_hint,
              channel_id = case when integrations.host = excluded.host
                                then integrations.channel_id end,
              channel_name = case when integrations.host = excluded.host
                                  then integrations.channel_name end,
              status = 'disconnected', last_error = null, updated_at = now()
            returning {_COLUMNS}""",
        {
            "tenant": tenant_id,
            "provider": PROVIDER,
            "host": host,
            "client_id": client_id,
            "secret": secret_encrypted,
            "hint": secret_hint,
            "settings": Jsonb(settings),
        },
    ).fetchone()


def update(conn: psycopg.Connection, **changes: Any) -> dict[str, Any] | None:
    """Set some of channel_id, channel_name, settings, status, last_error."""
    allowed = {"channel_id", "channel_name", "settings", "status", "last_error"}
    # The column names go into the SQL, so refuse anything else (not an assert:
    # python -O removes those).
    if not changes or not set(changes) <= allowed:
        raise ValueError(f"cannot update {sorted(set(changes) - allowed) or 'nothing'}")
    sets = ", ".join(f"{key} = %({key})s" for key in changes)
    params = {k: Jsonb(v) if k == "settings" else v for k, v in changes.items()}
    return conn.execute(
        f"""update integrations set {sets}, updated_at = now()
            where provider = %(provider)s returning {_COLUMNS}""",
        {**params, "provider": PROVIDER},
    ).fetchone()


def delete(conn: psycopg.Connection) -> bool:
    return conn.execute("delete from integrations where provider = %s", (PROVIDER,)).rowcount > 0


_EVENT = """id, response_id, verb, payload, test, status, attempts, last_error, liana_response,
            created_at, sent_at"""


def add_event(
    conn: psycopg.Connection,
    tenant_id: UUID,
    verb: str,
    payload: dict,
    test: bool,
    response_id: UUID | None = None,
) -> dict[str, Any]:
    return conn.execute(
        f"""insert into integration_events (tenant_id, provider, verb, payload, test, response_id)
            values (%s, %s, %s, %s, %s, %s) returning {_EVENT}""",
        (tenant_id, PROVIDER, verb, Jsonb(payload), test, response_id),
    ).fetchone()


def event_for_request(conn: psycopg.Connection, contact_request_id: UUID) -> dict[str, Any] | None:
    """The sync log row of a "Contact me" request, so a redelivered message reuses it."""
    return conn.execute(
        f"""select {_EVENT} from integration_events
            where provider = %s and verb = 'survey_contact_request'
              and payload -> 'events' -> 0 -> 'items' ->> 'contact_request_id' = %s
            order by created_at limit 1""",
        (PROVIDER, str(contact_request_id)),
    ).fetchone()


def log_answer_event(
    conn: psycopg.Connection,
    tenant_id: UUID,
    response_id: UUID,
    verb: str,
    payload: dict,
    status: str,
    error: str | None,
) -> dict[str, Any] | None:
    """The response's row in the sync log, made or changed for this answer. None when
    there is nothing new to do: the row already has this payload and is sent, being
    sent or deliberately not sent. A changed answer (new payload) or a failed row
    starts again with `status`."""
    return conn.execute(
        f"""insert into integration_events
              (tenant_id, provider, response_id, verb, payload, status, last_error)
            values (%(tenant)s, %(provider)s, %(response)s, %(verb)s, %(payload)s, %(status)s,
                    %(error)s)
            on conflict (response_id, verb) where response_id is not null do update set
              payload = excluded.payload, status = excluded.status,
              last_error = excluded.last_error
            where integration_events.payload is distinct from excluded.payload
               or integration_events.status in ('failed', 'retrying')
            returning {_EVENT}""",
        {
            "tenant": tenant_id,
            "provider": PROVIDER,
            "response": response_id,
            "verb": verb,
            "payload": Jsonb(payload),
            "status": status,
            "error": error,
        },
    ).fetchone()


def give_up_event(
    conn: psycopg.Connection,
    error: str,
    *,
    contact_request_id: UUID | None = None,
    response_id: UUID | None = None,
) -> dict[str, Any] | None:
    """Move a "Contact me" request's or an answer's retrying row to failed, once the
    connector stops retrying it. None when the row is not retrying (sent meanwhile,
    or already failed)."""
    return conn.execute(
        f"""update integration_events set status = 'failed', last_error = %(error)s
            where provider = %(provider)s and status = 'retrying'
              and ((%(request)s::text is not null and verb = 'survey_contact_request'
                    and payload -> 'events' -> 0 -> 'items' ->> 'contact_request_id'
                        = %(request)s)
                or (%(response)s::uuid is not null and response_id = %(response)s
                    and verb = 'survey_answered'))
            returning {_EVENT}""",
        {
            "error": error,
            "provider": PROVIDER,
            "request": str(contact_request_id) if contact_request_id else None,
            "response": response_id,
        },
    ).fetchone()


def get_event(conn: psycopg.Connection, event_id: UUID) -> dict[str, Any] | None:
    return conn.execute(
        f"select {_EVENT} from integration_events where id = %s and provider = %s",
        (event_id, PROVIDER),
    ).fetchone()


def claim_event(conn: psycopg.Connection, event_id: UUID) -> dict[str, Any] | None:
    """Move a failed or retrying event to pending for one retry. None when another
    request got it first, or it was sent meanwhile."""
    return conn.execute(
        f"""update integration_events set status = 'pending'
            where id = %s and provider = %s and status in ('failed', 'retrying')
            returning {_EVENT}""",
        (event_id, PROVIDER),
    ).fetchone()


def finish_event(
    conn: psycopg.Connection,
    event_id: UUID,
    status: str,
    error: str | None,
    response: str | None = None,
) -> dict[str, Any]:
    """Count one attempt and store its outcome, with LianaAutomation's answer (status
    and body) when there was one."""
    return conn.execute(
        f"""update integration_events
            set status = %(status)s, attempts = attempts + 1, last_error = %(error)s,
                liana_response = coalesce(%(response)s, liana_response),
                sent_at = case when %(status)s = 'sent' then now() else sent_at end
            where id = %(id)s returning {_EVENT}""",
        {"status": status, "error": error, "response": response, "id": event_id},
    ).fetchone()


def mark_event(
    conn: psycopg.Connection, event_id: UUID, status: str, reason: str | None
) -> dict[str, Any]:
    """Set the status without counting an attempt: nothing was sent (e.g. the
    contact's email address could not be looked up)."""
    return conn.execute(
        f"""update integration_events set status = %s, last_error = %s
            where id = %s returning {_EVENT}""",
        (status, reason, event_id),
    ).fetchone()


def set_payload(conn: psycopg.Connection, event_id: UUID, payload: dict) -> None:
    """The payload with the contact's email address, once LianaMailer gave it."""
    conn.execute(
        "update integration_events set payload = %s where id = %s", (Jsonb(payload), event_id)
    )


# --- LianaMailer contact ids and email addresses ---------------------------------


def cached_email(conn: psycopg.Connection, contact_id: str, max_age: timedelta) -> str | None:
    """The address LianaMailer gave for this contact id lately, or None."""
    row = conn.execute(
        """select email from lianamailer_contacts
           where contact_id = %s and fetched_at > now() - %s""",
        (contact_id, max_age),
    ).fetchone()
    return row["email"] if row else None


def cache_email(conn: psycopg.Connection, contact_id: str, email: str, max_age: timedelta) -> None:
    """Remember the address for a while; forget addresses older than that."""
    conn.execute("delete from lianamailer_contacts where fetched_at <= now() - %s", (max_age,))
    conn.execute(
        """insert into lianamailer_contacts (tenant_id, contact_id, email)
           values (app_tenant_id(), %s, %s)
           on conflict (tenant_id, contact_id) do update
             set email = excluded.email, fetched_at = now()""",
        (contact_id, email),
    )


def save_contact_email(conn: psycopg.Connection, response_id: UUID, email: str) -> None:
    """The address of a reader who asked to be contacted, for Results -> Responses.
    Only on responses with "Contact me": other answers never keep an address."""
    conn.execute(
        """update responses set contact_email = %s
           where id = %s and contact_requested and contact_email is distinct from %s""",
        (email, response_id, email),
    )


def events(conn: psycopg.Connection, status: str | None, limit: int) -> list[dict[str, Any]]:
    """The sync log, newest first."""
    return conn.execute(
        f"""select {_EVENT} from integration_events
            where provider = %s and (%s::text is null or status = %s)
            order by created_at desc, id desc limit %s""",
        (PROVIDER, status, status, limit),
    ).fetchall()


def event_counts(conn: psycopg.Connection) -> dict[str, int]:
    return {
        row["status"]: row["n"]
        for row in conn.execute(
            """select status, count(*)::integer as n from integration_events
               where provider = %s group by status""",
            (PROVIDER,),
        ).fetchall()
    }
