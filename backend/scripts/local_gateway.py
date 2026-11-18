"""Loopback-only development gateway for the native Python service apps."""

import asyncio
import logging
import os

from starlette.responses import JSONResponse

from data_analyzer.main import app as analyzer
from liana_survey_shared.config import get_settings
from liana_survey_shared.web.auth import demo_user
from respondent_service.main import app as respondent
from survey_manager.main import app as surveys

IDENTITY = {b"x-tenant-id", b"x-user-id", b"x-tenant-name", b"x-user-name", b"x-user-email"}


class DirectLianaEvents:
    """Local development without RabbitMQ: hands each "new responses" email
    straight to the connector's code with its mock adapters, instead of putting
    it on survey.liana-events. The mock mail shows up in this terminal."""

    def __init__(self) -> None:
        from liana_connector.factory import build_contact_events, build_notification_mail

        self.contacts = build_contact_events(get_settings())
        self.mail = build_notification_mail(get_settings())

    async def publish(self, message) -> None:
        from liana_connector.handlers import handle_event

        handle_event(message.model_dump_json().encode(), self.contacts, self.mail)


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
        if recorded.digest is not None and self.events is not None:
            await self.events.publish(recorded.digest)

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
    if path == "/api/v1/me":
        await JSONResponse(demo_user().model_dump(mode="json"))(scope, receive, send)
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
        ("/r", respondent),
    ):
        if path == prefix or path.startswith(prefix + "/"):
            target = service
    if target is None:
        await JSONResponse({"detail": "Not found"}, 404)(scope, receive, send)
        return
    # Never trust identity headers supplied by the browser, including public requests.
    headers = [(key, value) for key, value in scope["headers"] if key.lower() not in IDENTITY]
    if not (path == "/r" or path.startswith("/r/")):
        user = demo_user()
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
