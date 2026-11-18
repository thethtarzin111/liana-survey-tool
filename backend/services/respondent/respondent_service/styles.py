"""Reader-page tokens and styles from the prototype's survey preview."""

READER_STYLES = """
:root {
  --reader-text: #1d2433; --reader-muted: #696f77; --reader-line: #dfe3e7;
  --reader-surface: #ffffff; --reader-bg: #f6f7f9;
  --reader-font: 16px; --reader-title: 24px; --reader-small: 13px;
  --reader-radius: 14px; --reader-control-radius: 8px;
}
* { box-sizing: border-box; }
body { margin: 0; min-height: 100vh; padding: 32px 16px;
  color: var(--reader-text); font: var(--reader-font)/1.5 Arial, Helvetica, sans-serif;
  background: var(--reader-background, var(--reader-bg)); }
main { width: 100%; max-width: 620px; margin: 0 auto; padding: 28px;
  border: 1px solid var(--reader-line); border-radius: var(--reader-radius);
  background: var(--reader-surface); box-shadow: 0 3px 3px rgb(0 0 0 / 3%); }
h1 { margin: 0 0 8px; font-size: var(--reader-title); line-height: 1.25; }
main > p { margin: 0 0 24px; color: var(--reader-muted); white-space: pre-wrap; }
fieldset { min-width: 0; border: 0; padding: 0; margin: 24px 0; }
legend { margin-bottom: 12px; padding: 0; font-weight: 600; }
fieldset label { display: flex; gap: 10px; align-items: center; padding: 10px 14px;
  margin: 8px 0; border: 1px solid var(--reader-line);
  border-radius: var(--reader-control-radius); cursor: pointer; }
fieldset label:has(input:checked) { border-color: var(--reader-accent);
  background: color-mix(in srgb, var(--reader-accent) 8%, white); }
input { accent-color: var(--reader-accent); }
textarea { width: 100%; min-height: 100px; padding: 12px; resize: vertical;
  color: inherit; font: inherit; border: 1px solid var(--reader-line);
  border-radius: var(--reader-control-radius); }
button { min-height: 40px; padding: 10px 22px; margin: 8px 8px 0 0;
  border: 1px solid var(--reader-accent); border-radius: 120px;
  background: var(--reader-accent); color: white; font: inherit;
  font-weight: 600; cursor: pointer; }
button[type=button] { background: var(--reader-surface); color: var(--reader-text);
  border-color: var(--reader-line); }
button:disabled { opacity: .5; cursor: default; }
[hidden] { display: none !important; }
:focus-visible { outline: 2px solid var(--reader-accent); outline-offset: 3px; }
progress { height: 8px; accent-color: var(--reader-accent); border: 0;
  border-radius: 120px; overflow: hidden; background: var(--reader-line); }
progress::-webkit-progress-bar { background: var(--reader-line); }
progress::-webkit-progress-value { background: var(--reader-accent); }
#progress-text { font-size: var(--reader-small); color: var(--reader-muted); }
@media(max-width:480px) { body { padding: 16px 12px; } main { padding: 22px 18px; } }
"""
