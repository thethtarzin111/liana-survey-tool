"""Public survey rendering and validation. No internal survey names in template pages."""
# ruff: noqa: E501

import html
import json

from liana_survey_shared.messages import AnswerValue


def render(survey: dict, questions: list[dict], key: str) -> str:
    escape = html.escape
    title = survey["title"] if survey["type"] == "custom" else survey["reader_title"] or "Survey"
    fields = []
    for question in questions:
        name = str(question["id"])
        required = " required" if question["required"] else ""
        kind = question["kind"]
        options = question["options"]
        if kind in {"nps", "rating", "thumbs"}:
            options = (
                list(range(11))
                if kind == "nps"
                else list(range(1, 6))
                if kind == "rating"
                else ["Not for me", "Good", "Loved it"]
            )
        if options:
            multiple = kind in {"multiple_choice", "reasons"}
            controls = "".join(
                f'<label><input type="{"checkbox" if multiple else "radio"}" name="{name}" value="{escape(str(index if kind == "thumbs" else option))}"{required if not multiple else ""}>{escape(str(option))}</label>'
                for index, option in enumerate(options)
            )
        else:
            controls = f'<textarea name="{name}" maxlength="{5000 if kind == "long_text" else 500}"{required}></textarea>'
        conditional = " data-reasons" if survey["type"] == "thumbs" and kind == "reasons" else ""
        fields.append(
            f"<fieldset{conditional}><legend>{escape(question['prompt'])}</legend>{controls}</fieldset>"
        )
    config = json.dumps({"key": key}).replace("<", "\\u003c")
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title>
<style>body{{font:16px/1.5 Arial;margin:24px;background:{survey["background_color"]}}}main{{max-width:650px;margin:auto;background:white;padding:24px}}label{{display:block;margin:8px}}fieldset{{margin:20px 0}}textarea{{width:95%;min-height:70px}}button{{padding:12px 24px}}</style>
<main><h1>{escape(title)}</h1><p>{escape(survey["description"] or "")}</p><form>{"".join(fields)}<button>Submit</button><p role="alert" id="error"></p></form></main>
<script>const config={config};const form=document.querySelector('form');function conditional(){{const first=form.querySelector('input:checked');form.querySelectorAll('[data-reasons]').forEach(group=>{{group.hidden=!first||first.value!=='0';group.querySelectorAll('input').forEach(input=>input.disabled=group.hidden);}});}}form.addEventListener('change',conditional);conditional();form.addEventListener('submit',async event=>{{event.preventDefault();const answers={{}};for(const [key,value] of new FormData(form)){{(answers[key]??=[]).push(value);}}const button=form.querySelector('button');button.disabled=true;try{{const response=await fetch(location.pathname+'/submit'+location.search,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{key:config.key,answers}})}});if(!response.ok)throw new Error('Please check your answers and try again.');document.open();document.write(await response.text());document.close();}}catch(error){{document.getElementById('error').textContent=error.message;button.disabled=false;}}}});</script></html>"""


def validate(questions: list[dict], raw: dict, survey_type: str) -> list[AnswerValue]:
    result = []
    main = raw.get(str(questions[0]["id"]), []) if questions else []
    for question in questions:
        kind = question["kind"]
        if survey_type == "thumbs" and kind == "reasons" and main != ["0"]:
            continue
        values = raw.get(str(question["id"]), [])
        if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
            raise ValueError("Invalid answer")
        values = [v.strip() for v in values if v.strip()]
        if not values:
            if question["required"]:
                raise ValueError("Answer every required question")
            continue
        answer = AnswerValue(question_id=question["id"])
        if kind in {"nps", "rating", "thumbs"}:
            scale = range(11) if kind == "nps" else range(1, 6) if kind == "rating" else range(3)
            if len(values) != 1 or values[0] not in [str(v) for v in scale]:
                raise ValueError("Invalid rating")
            answer.number = int(values[0])
        elif kind in {"text", "long_text"}:
            if len(values) != 1 or len(values[0]) > (5000 if kind == "long_text" else 500):
                raise ValueError("Invalid text")
            answer.text = values[0]
        else:
            if any(v not in question["options"] for v in values):
                raise ValueError("Invalid choice")
            if kind in {"single_choice", "dropdown"} and len(values) != 1:
                raise ValueError("Choose one answer")
            answer.choices = list(dict.fromkeys(values))
        result.append(answer)
    return result
