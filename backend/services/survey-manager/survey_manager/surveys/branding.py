"""Branding rules (#66): colours and logos. Plain Python, no SQL or HTTP."""

import html
import re

MAX_LOGO_BYTES = 1024 * 1024  # 1 MB
#: The prototype accepts PNG, JPG, SVG and WebP ("image/png,image/jpeg,image/svg+xml,image/webp").
LOGO_TYPES = ("image/png", "image/jpeg", "image/svg+xml", "image/webp")
DEFAULT_ACCENT = "#0F6A5E"  # Teal
DEFAULT_BACKGROUND = "#FFFFFF"  # White

_HEX = re.compile(r"#?([0-9a-fA-F]{6})")
# Things an SVG may not contain, so a logo can never run code or pull in other
# content. This is a second line of defence: logos are shown with <img> (which
# never runs SVG scripts) and served with a sandboxing Content-Security-Policy.
_SVG_ACTIVE = re.compile(
    r"<\s*(script|foreignObject|iframe|embed|object|animate|set|handler)\b"
    # <use> is common in exported logos for shapes in the same file (href="#id");
    # only references to anything outside the file are refused.
    r"|<\s*use\b[^>]*\bhref\s*=\s*[\"'](?!#)"
    r"|\bon[a-z]+\s*="
    r"|javascript\s*:|data\s*:\s*text/html",
    re.I,
)


class LogoError(ValueError):
    """The file is not an accepted logo."""


class LogoTooLarge(LogoError):
    """The file is bigger than MAX_LOGO_BYTES."""


def normalise_colour(value: str) -> str:
    """Turn "#2b6450" or "2B6450" into "#2B6450". Raises ValueError for anything else."""
    match = _HEX.fullmatch(value.strip()) if isinstance(value, str) else None
    if not match:
        raise ValueError("use a 6-digit hex code, like #2B6450")
    return f"#{match.group(1).upper()}"


def check_logo(content_type: str, data: bytes) -> str:
    """Return the logo's content type, or raise LogoError / LogoTooLarge.

    The bytes must match the declared type, so a renamed file is refused."""
    kind = content_type.split(";")[0].strip().lower()
    if kind == "image/jpg":
        kind = "image/jpeg"
    if kind not in LOGO_TYPES:
        raise LogoError("choose a PNG, JPG, SVG or WebP image")
    if not data:
        raise LogoError("the file is empty")
    if len(data) > MAX_LOGO_BYTES:
        raise LogoTooLarge("the logo can be at most 1 MB")

    if kind == "image/png" and not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise LogoError("the file is not a PNG image")
    if kind == "image/jpeg" and not data.startswith(b"\xff\xd8\xff"):
        raise LogoError("the file is not a JPG image")
    if kind == "image/webp" and not (data[:4] == b"RIFF" and data[8:12] == b"WEBP"):
        raise LogoError("the file is not a WebP image")
    if kind == "image/svg+xml":
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as error:
            raise LogoError("the file is not an SVG image") from error
        if "<svg" not in text.lower():
            raise LogoError("the file is not an SVG image")
        # Decode entities first, so "&#106;avascript:" is caught too.
        if _SVG_ACTIVE.search(html.unescape(text)):
            raise LogoError("SVG logos cannot contain scripts or event handlers")
    return kind
