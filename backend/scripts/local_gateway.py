"""Loopback-only development gateway for the native Python service apps."""

import asyncio
import os

from starlette.responses import JSONResponse

from data_analyzer.main import app as analyzer
from liana_survey_shared.config import get_settings
from liana_survey_shared.web.auth import demo_user
from respondent_service.main import app as respondent
from survey_manager.main import app as surveys

IDENTITY = {b"x-tenant-id", b"x-user-id", b"x-tenant-name", b"x-user-name", b"x-user-email"}


class DirectAnswerQueue:
    """Local development without RabbitMQ: hands each answer straight to the
    worker's save code in this process, instead of putting it on survey.answers.
    The same code saves it as with the real queue (#23), so counting a reader
    once, refusing bad answers and tenant isolation all behave the same.
    Used unless LOCAL_QUEUE_WORKERS=1 (then a RabbitMQ and the worker run)."""

    async def publish(self, message) -> None:
        from survey_worker.handlers import handle_answer

        await asyncio.to_thread(handle_answer, message.model_dump_json().encode())

    async def close(self) -> None:
        pass


if os.environ.get("LOCAL_QUEUE_WORKERS") != "1":
    respondent.state.answer_queue = DirectAnswerQueue()


async def app(scope, receive, send):
    if scope["type"] == "lifespan":
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
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
