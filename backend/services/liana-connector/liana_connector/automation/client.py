"""Calls to the LianaAutomation API (OAuth 2.0 client credentials).

Endpoint paths and bodies follow the team's notes on the API (pingpong,
channel/list, channel/create, import). Check them against Liana's API docs once
there are real credentials; the response shapes are read defensively.

Every failure becomes one of four errors, which decide what the caller does:

    401 from the API   -> token refreshed and the call retried once, then AuthError
    400                -> PermanentError: bad data, do not retry
    404                -> ConfigError: wrong host, stop sending
    5xx, timeout, no connection -> TemporaryError: retry later
    200 that isn't JSON -> PermanentError (token service: TemporaryError)
"""

import itertools
import time
from typing import Any, Protocol

import httpx

from .domain import DEMO_HOST

TOKEN_URL = "https://tokens.lianacloud.com/token"
STAGING_TOKEN_URL = "https://tokens.stg.lianacloud.com/token"
SCOPE = "automation-api"


def token_url_for(host: str) -> str:
    """Liana's staging hosts (with a `stg` part, e.g. x.stg.lianacloud.com) get their
    tokens from the staging token service; every other host from production."""
    return STAGING_TOKEN_URL if "stg" in host.split(".") else TOKEN_URL


class LianaError(Exception):
    """A failed call. `str(error)` is safe to show to the admin."""

    kind = "error"


class AuthError(LianaError):
    kind = "auth"


class PermanentError(LianaError):
    kind = "bad_request"


class ConfigError(LianaError):
    kind = "config"


class TemporaryError(LianaError):
    kind = "temporary"


class AutomationClient(Protocol):
    def ping(self) -> None: ...
    def channels(self) -> list[dict[str, str]]: ...
    def create_channel(self, name: str) -> dict[str, str]: ...
    def import_events(self, body: dict[str, Any]) -> None: ...


def _channel(item: Any) -> dict[str, str] | None:
    """{"id", "name"} from one channel in a response, None when it has no id."""
    if not isinstance(item, dict):
        return None
    channel_id = item.get("id", item.get("channel_id"))
    if channel_id is None:
        return None
    return {"id": str(channel_id), "name": str(item.get("name") or item.get("title") or channel_id)}


def _items(body: Any) -> list[Any]:
    """The list in a response that is a list, or has one under items, channels or data."""
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        for key in ("items", "channels", "data"):
            if isinstance(body.get(key), list):
                return body[key]
    return []


class LianaClient:
    """One organisation's connection. Keeps its token until a minute before it expires."""

    def __init__(
        self,
        host: str,
        client_id: str,
        secret: str,
        *,
        token_url: str | None = None,
        http: httpx.Client | None = None,
        clock=time.monotonic,
    ) -> None:
        self.api = f"https://{host}/api/v1"
        self.client_id = client_id
        self.secret = secret
        self.token_url = token_url or token_url_for(host)
        self.http = http or httpx.Client(timeout=15)
        self.clock = clock
        self._token: str | None = None
        self._expires = 0.0

    def _access_token(self) -> str:
        if self._token and self.clock() < self._expires - 60:
            return self._token
        try:
            res = self.http.post(
                self.token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.secret,
                    "scope": SCOPE,
                },
            )
        except httpx.HTTPError as error:
            raise TemporaryError("Could not reach Liana's token service. Try again.") from error
        if res.status_code in (400, 401, 403):
            raise AuthError("Wrong client ID or secret, or the client lacks automation-api.")
        if res.status_code >= 500:
            raise TemporaryError(f"Liana's token service answered {res.status_code}. Try again.")
        if res.status_code != 200:
            raise AuthError(f"Liana's token service answered {res.status_code}.")
        try:
            body = res.json()
            token = body["access_token"]
            expires_in = float(body.get("expires_in", 900))
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            raise TemporaryError(
                "Liana's token service gave an unexpected answer. Try again."
            ) from error
        self._token = token
        self._expires = self.clock() + expires_in
        return self._token

    def _post(self, path: str, body: dict[str, Any]) -> Any:
        for attempt in (1, 2):
            try:
                res = self.http.post(
                    f"{self.api}/{path}",
                    json=body,
                    headers={"Authorization": f"Bearer {self._access_token()}"},
                )
            except httpx.TimeoutException as error:
                raise TemporaryError("Liana did not answer in time. Try again.") from error
            except httpx.ConnectError as error:
                # A DNS blip or an outage looks the same as a wrong host, so this is
                # temporary: it never marks a correct connection as broken. A wrong
                # host shows up as this message on every try, or as a 404.
                raise TemporaryError(
                    "Could not connect to the host. Check the host name, or try again later."
                ) from error
            except httpx.HTTPError as error:
                raise TemporaryError("The call to Liana failed. Try again.") from error
            if res.status_code == 401 and attempt == 1:
                self._token = None  # expired or revoked: get a new one and retry once
                continue
            if res.status_code == 401:
                raise AuthError("Liana refused the credentials (401).")
            if res.status_code == 400:
                raise PermanentError(f"Liana refused the data (400): {res.text[:300]}")
            if res.status_code == 404:
                raise ConfigError("Not found (404): check the host.")
            if res.status_code >= 500:
                raise TemporaryError(f"Liana answered {res.status_code}. Try again later.")
            if res.status_code >= 300:
                raise PermanentError(f"Liana answered {res.status_code}: {res.text[:300]}")
            if not res.content:
                return None
            try:
                return res.json()
            except ValueError as error:
                raise PermanentError(
                    f"Liana answered {path} with something that is not JSON."
                ) from error
        raise AssertionError("unreachable")

    def ping(self) -> None:
        self._post("pingpong", {"ping": "pong"})

    def channels(self) -> list[dict[str, str]]:
        return [c for c in map(_channel, _items(self._post("channel/list", {}))) if c]

    def create_channel(self, name: str) -> dict[str, str]:
        body = self._post("channel/create", {"name": name})
        created = _channel(body) or (
            _channel(body.get("channel")) if isinstance(body, dict) else None
        )
        if created is None:
            # Some APIs return only a status: look the new channel up by name.
            created = next((c for c in self.channels() if c["name"] == name), None)
        if created is None:
            raise PermanentError("Liana did not return the new channel.")
        return created

    def import_events(self, body: dict[str, Any]) -> None:
        self._post("import", body)


# --- Demo -------------------------------------------------------------------------

DEMO_CLIENT_ID = "demo-client"
DEMO_SECRET = "demo-secret"
_demo_channels: list[dict[str, str]] = [{"id": "demo-1", "name": "Website"}]
_demo_ids = itertools.count(2)


class DemoLianaClient:
    """A fake LianaAutomation for local development, so every step of the page can be
    tried without a Liana account. Client ID demo-client, secret demo-secret. A
    contact with "fail" in its email or contact id gets a temporary error, to try
    Retry."""

    def __init__(self, client_id: str, secret: str) -> None:
        self.ok = client_id == DEMO_CLIENT_ID and secret == DEMO_SECRET

    def _check(self) -> None:
        if not self.ok:
            raise AuthError(
                "Wrong client ID or secret. In demo mode use demo-client / demo-secret."
            )

    def ping(self) -> None:
        self._check()

    def channels(self) -> list[dict[str, str]]:
        self._check()
        return [dict(c) for c in _demo_channels]

    def create_channel(self, name: str) -> dict[str, str]:
        self._check()
        channel = {"id": f"demo-{next(_demo_ids)}", "name": name}
        _demo_channels.append(channel)
        return dict(channel)

    def import_events(self, body: dict[str, Any]) -> None:
        self._check()
        if not str(body.get("channel", "")).startswith("demo-"):
            raise PermanentError("Liana refused the data (400): unknown channel.")
        for item in body.get("data", []):
            if any("fail" in str(value) for value in (item.get("identity") or {}).values()):
                raise TemporaryError("Liana answered 503. Try again later. (demo)")


def build_client(host: str, client_id: str, secret: str, *, allow_demo: bool) -> AutomationClient:
    """The client for a saved connection. The demo host works only when allowed (dev
    mode): a demo row copied to another environment must never record "Sent" for events
    that never left the server."""
    if host == DEMO_HOST:
        if not allow_demo:
            raise ConfigError("The demo host only works in local development. Connect a real host.")
        return DemoLianaClient(client_id, secret)
    return LianaClient(host, client_id, secret)
