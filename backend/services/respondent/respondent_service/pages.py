"""The plain, server-rendered pages readers see (#42). No JavaScript.

Survey texts and colours are escaped; colours are only used when they are
6-digit hex codes, as stored by survey-manager.
"""

import html
import re

_HEX = re.compile(r"#[0-9A-Fa-f]{6}")
DEFAULT_ACCENT = "#0F6A5E"
DEFAULT_BACKGROUND = "#FFFFFF"
DEFAULT_THANKS = "Your answer was saved."


def _colour(value: str | None, default: str) -> str:
    return value if value and _HEX.fullmatch(value) else default


def page(heading: str, text: str, accent: str | None = None, background: str | None = None) -> str:
    accent_hex = _colour(accent, DEFAULT_ACCENT)
    background_hex = _colour(background, DEFAULT_BACKGROUND)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<link rel="icon" href="data:,">
<title>{html.escape(heading)}</title>
<style>
  body {{ margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center;
         background: {background_hex}; color: #353A40; font: 16px/1.5 Inter, Arial, sans-serif; }}
  main {{ max-width: 480px; margin: 24px; padding: 32px 28px; border-radius: 14px;
         background: #FFFFFF; border-top: 6px solid {accent_hex};
         box-shadow: 0 3px 12px rgba(0, 0, 0, 0.08); }}
  h1 {{ margin: 0 0 8px; font-size: 22px; }}
  p {{ margin: 0; }}
</style>
</head>
<body>
<main>
<h1>{html.escape(heading)}</h1>
<p>{html.escape(text)}</p>
</main>
</body>
</html>
"""


def thank_you(message: str | None, accent: str | None, background: str | None) -> str:
    return page("Thank you!", (message or "").strip() or DEFAULT_THANKS, accent, background)


def problem(text: str) -> str:
    return page("We couldn’t take this answer", text)
