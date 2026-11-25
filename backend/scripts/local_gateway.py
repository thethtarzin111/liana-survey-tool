"""Loopback-only development gateway for the native Python service apps.

Also runs the shared demo server (backend/infra/deploy/README.md), bound to
127.0.0.1 behind Caddy, which adds HTTPS. It gives every admin request a demo
user, so it is not a production entry point. Locally the user menu switches
between the demo organisations (a cookie picks the demo user). On the demo server
each organisation has a demo login (DEMO_LOGINS): the login page signs in and a
signed session cookie picks the demo user."""

import asyncio
import hashlib
import hmac
import logging
import os
import time

from pydantic import BaseModel, ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from data_analyzer.main import app as analyzer
from liana_connector.api import app as connector
from liana_survey_shared.config import get_settings
from liana_survey_shared.web.auth import CurrentUser, demo_user, demo_users
from respondent_service.main import app as respondent
from survey_manager.main import app as surveys

IDENTITY = {
    b"x-tenant-id",
    b"x-user-id",
    b"x-tenant-name",
    b"x-user-name",
    b"x-user-email",
}
DEMO_ORG_COOKIE = "demo_org"
SESSION_COOKIE = "demo_session"
ONE_YEAR = 365 * 24 * 60 * 60
SESSION_SECONDS = 7 * 24 * 60 * 60


class OrganizationChoice(BaseModel):
    tenant_id: str


class LoginForm(BaseModel):
    email: str
    password: str


class DemoLogin(BaseModel):
    user: CurrentUser
    password: str


def demo_logins() -> dict[str, DemoLogin] | None:
    """The demo server's logins by email address, from
    DEMO_LOGINS="<demo tenant id>=<password>,...". Each login is that organisation's
    demo user. None means there are no logins: locally, the user menu picks the
    organisation and everyone stays signed in."""
    setting = os.environ.get("DEMO_LOGINS", "").strip()
    if not setting:
        return None
    users = {str(u.tenant_id): u for u in demo_users()}
    logins = {}
    for entry in setting.split(","):
        tenant_id, _, password = entry.strip().partition("=")
        user = users.get(tenant_id.strip())
        if user is None or not password:
            raise RuntimeError(f"DEMO_LOGINS: {entry!r} is not <demo tenant id>=<password>")
        logins[user.email.lower()] = DemoLogin(user=user, password=password)
    return logins


def session_key() -> bytes:
    key = os.environ.get("DEMO_SESSION_SECRET", "")
    if len(key) < 32:
        raise RuntimeError("DEMO_SESSION_SECRET: set at least 32 characters with DEMO_LOGINS")
    return key.encode()


def session_signature(login: DemoLogin, expires: int) -> str:
    # Signed with the password too, so a new password ends the old sessions.
    message = f"{login.user.tenant_id}.{expires}.{login.password}".encode()
    return hmac.new(session_key(), message, hashlib.sha256).hexdigest()


def session_cookie(login: DemoLogin) -> str:
    expires = int(time.time()) + SESSION_SECONDS
    return f"{login.user.tenant_id}.{expires}.{session_signature(login, expires)}"


def session_user(cookie: str, logins: dict[str, DemoLogin]) -> CurrentUser | None:
    """The demo user of a session cookie, or None if it is forged, expired, for an
    organisation that no longer has a login, or from before a password change."""
    tenant_id, _, rest = cookie.partition(".")
    expires, _, signature = rest.partition(".")
    if not expires.isdigit() or int(expires) < time.time():
        return None
    login = next((x for x in logins.values() if str(x.user.tenant_id) == tenant_id), None)
    if login is None or not hmac.compare_digest(signature, session_signature(login, int(expires))):
        return None
    return login.user


def signed_in(request: Request) -> CurrentUser | None:
    """The demo user for this request, or None if the request has no valid login.
    On the demo server the session cookie decides. Locally the organisation chosen
    in the user menu decides, and an unknown or missing choice falls back to the default."""
    logins = demo_logins()
    if logins is not None:
        return session_user(request.cookies.get(SESSION_COOKIE, ""), logins)
    chosen = request.cookies.get(DEMO_ORG_COOKIE)
    return next((u for u in demo_users() if str(u.tenant_id) == chosen), demo_user())


def behind_https(request: Request) -> bool:
    # The demo server is behind Caddy, which adds HTTPS.
    return request.headers.get("x-forwarded-proto") == "https"


async def login(request: Request) -> Response:
    """POST signs in with a demo login and sets the session cookie."""
    if request.method != "POST":
        return JSONResponse({"detail": "Method not allowed"}, 405, headers={"Allow": "POST"})
    logins = demo_logins()
    if logins is None:
        return JSONResponse({"detail": "No demo logins here: you are always signed in"}, 404)
    try:
        form = LoginForm.model_validate_json(await request.body())
    except ValidationError:
        return JSONResponse({"detail": 'Send {"email": "...", "password": "..."}'}, 422)
    found = logins.get(form.email.strip().lower())
    # Compare even for an unknown email, so the answer takes as long either way.
    expected = found.password if found else "-"
    matches = hmac.compare_digest(form.password.encode(), expected.encode())
    if not matches or found is None:
        return JSONResponse({"detail": "Wrong email address or password"}, 401)
    response = JSONResponse(found.user.model_dump(mode="json"))
    response.set_cookie(
        SESSION_COOKIE,
        session_cookie(found),
        max_age=SESSION_SECONDS,
        httponly=True,
        samesite="lax",
        secure=behind_https(request),
    )
    return response


async def logout(request: Request) -> Response:
    """POST signs out. login_required tells the app whether to show the login page:
    locally there are no logins, so everyone stays signed in."""
    if request.method != "POST":
        return JSONResponse({"detail": "Method not allowed"}, 405, headers={"Allow": "POST"})
    response = JSONResponse({"login_required": demo_logins() is not None})
    response.delete_cookie(
        SESSION_COOKIE, httponly=True, samesite="lax", secure=behind_https(request)
    )
    return response


async def organizations(request: Request, current: CurrentUser) -> Response:
    """GET lists the demo organisations. PUT switches to one, for this browser.
    With demo logins, each login has one organisation and cannot switch."""
    logins = demo_logins()
    choices = [current] if logins is not None else demo_users()
    if request.method == "GET":
        return JSONResponse(
            [
                {
                    "tenant_id": str(u.tenant_id),
                    "tenant_name": u.tenant_name,
                    "user_name": u.name,
                    "current": u.tenant_id == current.tenant_id,
                }
                for u in choices
            ]
        )
    if request.method != "PUT":
        return JSONResponse({"detail": "Method not allowed"}, 405, headers={"Allow": "GET, PUT"})
    if logins is not None:
        return JSONResponse({"detail": "Sign in with the other organisation's login"}, 403)
    try:
        choice = OrganizationChoice.model_validate_json(await request.body())
    except ValidationError:
        return JSONResponse({"detail": 'Send {"tenant_id": "..."}'}, 422)
    user = next((u for u in demo_users() if str(u.tenant_id) == choice.tenant_id), None)
    if user is None:
        return JSONResponse({"detail": "Unknown demo organisation"}, 422)
    response = JSONResponse(user.model_dump(mode="json"))
    response.set_cookie(
        DEMO_ORG_COOKIE,
        str(user.tenant_id),
        max_age=ONE_YEAR,
        httponly=True,
        samesite="lax",
        secure=behind_https(request),
    )
    return response


class DirectLianaEvents:
    """Local development without RabbitMQ: hands each message for the connector
    (saved answers, "Contact me" requests, "new responses" emails) straight to the
    connector's code, instead of putting it on survey.liana-events. The adapters
    are the ones LIANA_ADAPTER and NOTIFICATION_MAIL_ADAPTER pick; the mock mail
    shows up in this terminal."""

    def __init__(self) -> None:
        from liana_connector.factory import build_contact_events, build_notification_mail

        self.contacts = build_contact_events(get_settings())
        self.mail = build_notification_mail(get_settings())

    async def publish(self, message) -> None:
        from liana_connector.handlers import deliver
        from liana_connector.retry import MAX_ATTEMPTS

        # Without RabbitMQ nothing would retry later, so this is the last attempt: a
        # temporary error makes the sync log row failed at once, with Retry, instead
        # of "retrying" for ever. The LianaAutomation adapter calls Liana over HTTP:
        # off the event loop.
        await asyncio.to_thread(
            deliver, message.model_dump_json().encode(), MAX_ATTEMPTS, self.contacts, self.mail
        )


class DirectAnswerQueue:
    """Local development without RabbitMQ: hands each answer straight to the
    worker's save code in this process, instead of putting it on survey.answers.
    The same code saves it as with the real queue (#23), so counting a reader
    once, refusing bad answers and tenant isolation all behave the same.
    Used unless LOCAL_QUEUE_WORKERS=1 (then a RabbitMQ and the worker run)."""

    def __init__(self, events: DirectLianaEvents | None = None) -> None:
        self.events = events

    async def publish(self, message) -> None:
        from survey_worker.handlers import record_answer

        recorded = await asyncio.to_thread(record_answer, message.model_dump_json().encode())
        if self.events is None:
            return
        for event in (*recorded.events, recorded.digest):
            if event is None:
                continue
            try:
                await self.events.publish(event)
            except Exception:
                # As the worker: the answer stays saved; the sync log shows the failure.
                logging.getLogger("liana_connector").exception(
                    "could not pass on %s", type(event).__name__
                )

    async def close(self) -> None:
        pass


# Without RabbitMQ the worker process does not run, so this process also runs
# its sweep for held "new responses" emails.
direct_events: DirectLianaEvents | None = None
if os.environ.get("LOCAL_QUEUE_WORKERS") != "1":
    direct_events = DirectLianaEvents()
    respondent.state.answer_queue = DirectAnswerQueue(direct_events)
    # Uvicorn only sets up its own loggers; show the worker's and the mock mail's.
    for name in ("survey_worker", "liana_connector"):
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)


async def app(scope, receive, send):
    if scope["type"] == "lifespan":
        sweeper = None
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                if direct_events is not None:
                    from survey_worker.digests import sweep_forever

                    sweeper = asyncio.create_task(sweep_forever(direct_events.publish))
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                if sweeper is not None:
                    sweeper.cancel()
                await send({"type": "lifespan.shutdown.complete"})
                return
    if scope["type"] != "http":
        return
    path = scope["path"]
    if get_settings().auth_mode != "dev":
        await JSONResponse({"detail": "Local gateway requires AUTH_MODE=dev"}, 403)(
            scope, receive, send
        )
        return
    request = Request(scope, receive)
    if path == "/api/v1/auth/login":
        await (await login(request))(scope, receive, send)
        return
    if path == "/api/v1/auth/logout":
        await (await logout(request))(scope, receive, send)
        return
    # Survey links and the health checks (deploy.sh) need no login.
    public = path in {"/r", "/health", "/health/ready"} or path.startswith("/r/")
    user = None if public else signed_in(request)
    if user is None and not public:
        await JSONResponse({"detail": "Sign in with a demo login"}, 401)(scope, receive, send)
        return
    if path == "/api/v1/me":
        await JSONResponse(user.model_dump(mode="json"))(scope, receive, send)
        return
    if path == "/api/v1/me/organizations":
        await (await organizations(request, user))(scope, receive, send)
        return
    if path == "/health":
        await JSONResponse({"status": "ok", "service": "local-gateway"})(scope, receive, send)
        return
    target = None
    if path in {"/health/ready", "/docs", "/docs/oauth2-redirect", "/openapi.json", "/redoc"}:
        target = surveys
    for prefix, service in (
        ("/api/v1/surveys", surveys),
        ("/api/v1/templates", surveys),
        ("/api/v1/results", analyzer),
        ("/api/v1/integrations", connector),
        ("/r", respondent),
    ):
        if path == prefix or path.startswith(prefix + "/"):
            target = service
    if target is None:
        await JSONResponse({"detail": "Not found"}, 404)(scope, receive, send)
        return
    # Never trust identity headers supplied by the browser, including public requests.
    headers = [(key, value) for key, value in scope["headers"] if key.lower() not in IDENTITY]
    if user is not None:
        headers.extend(
            (key, str(value).encode("utf-8"))
            for key, value in (
                (b"x-tenant-id", user.tenant_id),
                (b"x-user-id", user.user_id),
                (b"x-tenant-name", user.tenant_name),
                (b"x-user-name", user.name),
                (b"x-user-email", user.email),
            )
        )
    await target({**scope, "headers": headers}, receive, send)
