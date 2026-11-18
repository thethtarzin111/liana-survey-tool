import json
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from respondent_service.public_form import render


def test_progress_updates_and_excludes_hidden_reasons():
    root = Path(__file__).resolve().parents[4]
    jsdom = root / "frontend/node_modules/jsdom"
    if not shutil.which("node") or not jsdom.exists():
        pytest.skip("Node and frontend dependencies required for DOM test")
    questions = [
        dict(id=uuid4(), kind="thumbs", prompt="Rate", options=[], required=True),
        dict(id=uuid4(), kind="reasons", prompt="Why", options=["Price"], required=False),
        dict(id=uuid4(), kind="text", prompt="More", options=[], required=False),
    ]
    markup = render(
        dict(
            title="Private",
            reader_title="Public",
            type="thumbs",
            description="",
            background_color="#FFFFFF",
        ),
        questions,
        "key",
    )
    script = r"""
const { JSDOM } = require(process.argv[1]);
let html = ''; process.stdin.on('data', chunk => html += chunk);
process.stdin.on('end', async () => {
  const dom = new JSDOM(html, { runScripts: 'dangerously' });
  const d = dom.window.document;
  const tick = () => new Promise(resolve => setImmediate(resolve));
  const value = () => d.querySelector('progress').value;
  const change = element => element.dispatchEvent(new dom.window.Event('change', {bubbles:true}));
  await tick(); const values = [value()];
  const good = d.querySelector('input[value="1"]'); good.checked=true; change(good);
  await tick(); values.push(value());
  const text = d.querySelector('textarea'); text.value='Feedback'; change(text);
  await tick(); values.push(value());
  text.value='  '; change(text); await tick(); values.push(value());
  const bad = d.querySelector('input[value="0"]'); bad.checked=true; change(bad);
  await tick(); values.push(value());
  console.log(JSON.stringify(values)); dom.window.close();
});
"""
    result = subprocess.run(
        ["node", "-e", script, str(jsdom)], input=markup, text=True, capture_output=True, check=True
    )
    assert json.loads(result.stdout) == [0, 50, 100, 50, 33]
