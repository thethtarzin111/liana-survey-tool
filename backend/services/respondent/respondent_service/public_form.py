"""Public survey rendering and validation. No internal survey names in template pages."""
# ruff: noqa: E501

import html
import json

from liana_survey_shared.messages import AnswerValue

from .styles import READER_STYLES


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
<style>{READER_STYLES} :root {{ --reader-background: {survey["background_color"]}; --reader-accent: {survey.get("accent_color", "#2B6450")}; }}</style>
<main><h1>{escape(title)}</h1><p>{escape(survey["description"] or "")}</p>
<div aria-label="Survey progress">
  <label for="survey-progress">Questions answered</label>
  <progress id="survey-progress" max="100" value="0" aria-describedby="progress-text" style="display:block;width:100%"></progress>
  <span id="progress-text" role="status">0% complete</span>
</div>
<form>{"".join(fields)}<button>Submit</button><p role="alert" id="error"></p></form></main>
<script>
(() => {{
  const form = document.querySelector('form');
  const all = [...form.querySelectorAll('fieldset')];
  if (!all.length) return;
  form.noValidate = true;
  let current = all[0];
  const submit = form.querySelector('button');
  const previous = document.createElement('button');
  previous.type = 'button'; previous.textContent = 'Previous';
  const next = document.createElement('button');
  next.type = 'button'; next.textContent = 'Next';
  const position = document.createElement('p'); position.setAttribute('role', 'status');
  // Keep Submit first in DOM for the existing submission handler.
  form.append(previous, next, position);
  const eligible = () => all.filter(group => !group.hidden);
  function show(focus = false) {{
    const groups = eligible();
    if (!groups.includes(current)) current = groups[0];
    all.forEach(group => group.style.display = group === current ? '' : 'none');
    const index = groups.indexOf(current);
    previous.disabled = index <= 0;
    const last = index === groups.length - 1;
    if (next.hidden !== last) next.hidden = last;
    if (submit.hidden !== !last) submit.hidden = !last;
    position.textContent = `Question ${{index + 1}} of ${{groups.length}}`;
    if (focus) {{ const legend = current.querySelector('legend'); legend.tabIndex = -1; legend.focus(); }}
  }}
  function valid(group) {{
    return [...group.querySelectorAll('input,textarea,select')].every(control => control.reportValidity());
  }}
  next.addEventListener('click', () => {{
    if (!valid(current)) return;
    const groups = eligible(); current = groups[groups.indexOf(current) + 1] || current; show(true);
  }});
  previous.addEventListener('click', () => {{
    const groups = eligible(); current = groups[Math.max(0, groups.indexOf(current) - 1)]; show(true);
  }});
  form.addEventListener('submit', event => {{
    const groups = eligible();
    if (current !== groups.at(-1)) {{ event.preventDefault(); event.stopImmediatePropagation(); next.click(); return; }}
    for (const group of groups) {{
      if ([...group.querySelectorAll('input,textarea,select')].some(control => !control.checkValidity())) {{
        event.preventDefault(); event.stopImmediatePropagation(); current = group; show(true); valid(group); return;
      }}
    }}
  }}, true);
  new MutationObserver(() => show()).observe(form, {{subtree:true, attributes:true, attributeFilter:['hidden']}});
  show();
}})();
</script>
<script>
(() => {{
  const surveyForm = document.querySelector('form');
  const progress = document.getElementById('survey-progress');
  const text = document.getElementById('progress-text');
  function updateProgress() {{
    const questions = [...surveyForm.querySelectorAll('fieldset')].filter(group => !group.hidden);
    const answered = questions.filter(group => [...group.querySelectorAll('input,textarea,select')].some(control => {{
      if (control.disabled) return false;
      if (control.type === 'radio' || control.type === 'checkbox') return control.checked;
      return control.value.trim().length > 0 && control.checkValidity();
    }})).length;
    const percentage = questions.length ? Math.round(answered / questions.length * 100) : 0;
    progress.value = percentage;
    text.textContent = `${{answered}} of ${{questions.length}} questions answered (${{percentage}}% complete)`;
  }}
  // Run after conditional-question handlers so hidden reasons never count.
  surveyForm.addEventListener('input', () => queueMicrotask(updateProgress));
  surveyForm.addEventListener('change', () => queueMicrotask(updateProgress));
  new MutationObserver(updateProgress).observe(surveyForm, {{subtree:true, attributes:true, attributeFilter:['hidden','disabled']}});
  queueMicrotask(updateProgress);
}})();
</script>
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
