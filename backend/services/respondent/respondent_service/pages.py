"""The server-rendered pages readers see: the thank-you and problem pages (#42) and
the survey link page (#105), which works as a plain HTML form.

Survey texts and colours are escaped; colours are only used when they are
6-digit hex codes, as stored by survey-manager. The styles use the values in
design/tokens.json (these pages are served without the app's CSS).
"""

import html
import re
from collections.abc import Mapping, Sequence
from typing import Any

from liana_survey_shared.texts import language_or_default, text

from .domain import field_name

_HEX = re.compile(r"#[0-9A-Fa-f]{6}")
DEFAULT_ACCENT = "#0F6A5E"
DEFAULT_BACKGROUND = "#FFFFFF"

# Tokens from design/tokens.json: text, textMuted, border, borderStrong, surface,
# error, radius.card / nav / pill, shadow.card, font.body / heading.
_STYLES = """
  * { box-sizing: border-box; }
  :root { --font: Inter, Helvetica, Arial, sans-serif; }
  body { margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center;
         background: var(--background); color: #353A40; font: 16px/1.5 var(--font); }
  main { width: 100%; max-width: 480px; margin: 24px; padding: 32px 28px; border-radius: 14px;
         background: #FFFFFF; border-top: 6px solid var(--accent);
         box-shadow: 0 3px 12px rgba(0, 0, 0, 0.08); }
  h1 { margin: 0 0 8px; font: 600 22px/1.3 Poppins, Helvetica, Arial, sans-serif; }
  p { margin: 0; }
  main.survey { max-width: 600px; }
  .description { color: #696F77; white-space: pre-line; }
  .error { margin-top: 16px; padding: 10px 14px; border-radius: 7px; color: #DB2828;
           background: #FFF6F6; border: 1px solid #DB2828; }
  form { display: flex; flex-direction: column; gap: 28px; margin-top: 24px; }
  fieldset { min-width: 0; margin: 0; padding: 0; border: 0; }
  legend { padding: 0; margin-bottom: 12px; font-weight: 600; }
  .optional, .hint { color: #696F77; font-weight: 400; }
  .hint { margin: -6px 0 10px; font-size: 14px; }
  label { position: relative; cursor: pointer; }
  .options { display: flex; flex-direction: column; gap: 8px; }
  .options label { display: flex; gap: 10px; align-items: center; padding: 10px 14px;
                   border: 1px solid #DFE3E7; border-radius: 7px; }
  .options input { margin: 0; accent-color: var(--accent); }
  .pills { display: flex; flex-wrap: wrap; gap: 8px; }
  .pills label { padding: 8px 16px; border: 1px solid #CED3D9; border-radius: 120px; }
  .scale { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 6px; }
  .scale-nps { grid-template-columns: repeat(11, minmax(0, 1fr)); gap: 4px; }
  .scale label { display: flex; flex-direction: column; align-items: center; padding: 8px 2px;
                 border: 1px solid #CED3D9; border-radius: 7px;
                 font-weight: 600; text-align: center; }
  .scale small { font-weight: 400; font-size: 12px; line-height: 1.3; }
  .ends { display: flex; justify-content: space-between; gap: 8px; margin-top: 6px;
          color: #696F77; font-size: 13px; }
  .pills input, .scale input { position: absolute; inset: 0; opacity: 0; margin: 0;
                               cursor: pointer; }
  .pills label:has(input:checked), .scale label:has(input:checked) {
    background: var(--accent); border-color: var(--accent); color: #FFFFFF; }
  .options label:has(input:checked) { border-color: var(--accent); }
  label:has(input:focus-visible) { outline: 2px solid var(--accent); outline-offset: 2px; }
  input[type=text], textarea, select { width: 100%; padding: 10px 12px;
         color: inherit; font: inherit;
         border: 1px solid #CED3D9; border-radius: 7px; background: #FFFFFF; }
  textarea { min-height: 110px; resize: vertical; }
  input[type=text]:focus-visible, textarea:focus-visible, select:focus-visible {
    outline: 2px solid var(--accent); outline-offset: 1px; }
  .submit { align-self: flex-start; min-height: 44px; padding: 10px 24px; border: 0;
            border-radius: 120px; background: var(--accent); color: #FFFFFF;
            font: 600 16px/1.2 var(--font);
            box-shadow: 0 3px 3px rgba(0, 0, 0, 0.1); cursor: pointer; }
  .submit:focus-visible { outline: 2px solid #353A40; outline-offset: 2px; }
  @media (max-width: 520px) {
    body { align-items: flex-start; }
    main { margin: 12px; padding: 24px 18px; }
    .scale-nps { grid-template-columns: repeat(6, minmax(0, 1fr)); }
    /* The 1-5 words do not fit side by side: one row per answer instead. */
    .scale:not(.scale-nps) { grid-template-columns: 1fr; }
    .scale:not(.scale-nps) label { flex-direction: row; gap: 12px; padding: 10px 14px; }
    .scale small { font-size: 14px; }
  }
"""


def _colour(value: str | None, default: str) -> str:
    return value if value and _HEX.fullmatch(value) else default


def _document(
    title: str,
    main: str,
    accent: str | None,
    background: str | None,
    language: str | None,
) -> str:
    accent_hex = _colour(accent, DEFAULT_ACCENT)
    background_hex = _colour(background, DEFAULT_BACKGROUND)
    return f"""<!doctype html>
<html lang="{language_or_default(language)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<link rel="icon" href="data:,">
<title>{html.escape(title)}</title>
<style>
  :root {{ --accent: {accent_hex}; --background: {background_hex}; }}
{_STYLES}</style>
</head>
<body>
{main}
</body>
</html>
"""


def page(
    heading: str,
    body: str,
    accent: str | None = None,
    background: str | None = None,
    language: str | None = None,
) -> str:
    main = f"<main>\n<h1>{html.escape(heading)}</h1>\n<p>{html.escape(body)}</p>\n</main>"
    return _document(heading, main, accent, background, language)


def thank_you(
    message: str | None, accent: str | None, background: str | None, language: str | None = None
) -> str:
    body = (message or "").strip() or text("thanks_default", language)
    return page(text("thanks_heading", language), body, accent, background, language)


def problem(body: str, language: str | None = None) -> str:
    return page(text("problem_heading", language), body, language=language)


def reader_title(survey: Mapping[str, Any]) -> str:
    """The title readers see. Template surveys keep their name private: only the
    separate reader title is shown. Custom surveys show their survey title."""
    if survey["type"] == "custom":
        return (survey["title"] or "").strip()
    return (survey.get("reader_title") or "").strip()


def survey_form(
    survey: Mapping[str, Any],
    questions: Sequence[Mapping[str, Any]],
    *,
    key: str,
    channel: str,
    sent: Mapping[str, Sequence[str]] | None = None,
    error: str | None = None,
) -> str:
    """The whole survey for a reader who came from a plain link or QR code (#105).

    `key` is the signed visit key the answers are sent back with; `sent` and
    `error` show the reader's answers again with what to fix."""
    language = survey["language"]
    sent = sent or {}
    title = reader_title(survey)
    description = (survey.get("description") or "").strip()
    parts = ['<main class="survey">']
    if title:
        parts.append(f"<h1>{html.escape(title)}</h1>")
    if description:
        parts.append(f'<p class="description">{html.escape(description)}</p>')
    if error:
        parts.append(f'<p class="error" role="alert">{html.escape(error)}</p>')
    parts.append('<form method="post">')
    parts.append(f'<input type="hidden" name="key" value="{html.escape(key)}">')
    parts.append(f'<input type="hidden" name="ch" value="{html.escape(channel)}">')
    for question in questions:
        parts.append(
            _question(survey["type"], question, sent.get(field_name(question), ()), language)
        )
    parts.append(
        f'<button type="submit" class="submit">{html.escape(text("submit", language))}</button>'
    )
    parts.append("</form>\n</main>")
    return _document(
        title or text("survey_heading", language),
        "\n".join(parts),
        survey["accent_color"],
        survey["background_color"],
        language,
    )


def _question(
    survey_type: str, question: Mapping[str, Any], sent: Sequence[str], language: str | None
) -> str:
    kind = question["kind"]
    name = field_name(question)
    required = bool(question["required"])
    attrs = f' data-kind="{kind}"'
    if required:
        attrs += " data-required"
    hint = ""
    if survey_type == "thumbs" and kind == "reasons":
        # Asked only after "Not for me"; without JavaScript the reader is told so.
        attrs += " data-reasons"
        note = html.escape(text("reasons_if_not_for_me", language))
        hint = f'<p class="hint" data-no-script>{note}</p>'
    optional = (
        ""
        if required
        else f' <span class="optional">{html.escape(text("optional", language))}</span>'
    )
    prompt = (question["prompt"] or "").strip()
    if not prompt and kind == "reasons" and survey_type in ("thumbs", "nps", "csat"):
        prompt = text(f"reasons_{survey_type}", language)
    legend = f'<legend id="{name}-label">{html.escape(prompt)}{optional}</legend>'
    controls = _controls(question, name, sent, required, language)
    return f"<fieldset{attrs}>{legend}{hint}{controls}</fieldset>"


def _controls(
    question: Mapping[str, Any],
    name: str,
    sent: Sequence[str],
    required: bool,
    language: str | None,
) -> str:
    kind = question["kind"]
    need = " required" if required else ""

    def choice(input_type: str, value: str, label: str, needed: str = "") -> str:
        checked = " checked" if value in sent else ""
        return (
            f'<label><input type="{input_type}" name="{name}" value="{html.escape(value)}"'
            f"{checked}{needed}>{label}</label>"
        )

    if kind == "thumbs":
        labels = [
            text("thumbs_down", language),
            text("thumbs_ok", language),
            text("thumbs_up", language),
        ]
        items = "".join(
            choice("radio", str(i), html.escape(label), need) for i, label in enumerate(labels)
        )
        return f'<div class="pills">{items}</div>'
    if kind == "nps":
        items = "".join(choice("radio", str(n), str(n), need) for n in range(11))
        ends = (
            '<div class="ends" aria-hidden="true">'
            f"<span>0 {html.escape(text('nps_low', language))}</span>"
            f"<span>10 {html.escape(text('nps_high', language))}</span></div>"
        )
        return f'<div class="scale scale-nps">{items}</div>{ends}'
    if kind == "rating":
        items = "".join(
            choice(
                "radio",
                str(n),
                f"{n}<small>{html.escape(text(f'csat_{n}', language))}</small>",
                need,
            )
            for n in range(1, 6)
        )
        return f'<div class="scale">{items}</div>'
    options = [str(option) for option in question["options"] or []]
    if kind == "single_choice":
        items = "".join(choice("radio", o, f"<span>{html.escape(o)}</span>", need) for o in options)
        return f'<div class="options">{items}</div>'
    if kind == "multiple_choice":
        items = "".join(choice("checkbox", o, f"<span>{html.escape(o)}</span>") for o in options)
        return f'<div class="options">{items}</div>'
    if kind == "reasons":
        items = "".join(choice("checkbox", o, html.escape(o)) for o in options)
        return f'<div class="pills">{items}</div>'
    if kind == "dropdown":
        picked = sent[0] if sent else ""
        items = "".join(
            f'<option value="{html.escape(o)}"{" selected" if o == picked else ""}>'
            f"{html.escape(o)}</option>"
            for o in options
        )
        placeholder = f'<option value="">{html.escape(text("choose", language))}</option>'
        return (
            f'<select name="{name}" aria-labelledby="{name}-label"{need}>'
            f"{placeholder}{items}</select>"
        )
    value = html.escape(sent[0]) if sent else ""
    if kind == "long_text":
        return (
            f'<textarea name="{name}" maxlength="5000" aria-labelledby="{name}-label"{need}>'
            f"{value}</textarea>"
        )
    return (
        f'<input type="text" name="{name}" maxlength="500" value="{value}"'
        f' aria-labelledby="{name}-label"{need}>'
    )
