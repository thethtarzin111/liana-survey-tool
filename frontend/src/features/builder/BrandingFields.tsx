import { useEffect, useId, useRef, useState } from 'react';
import { api, type Survey } from '../../api/client';
import { Button, useToast } from '../../components/ui';
import {
  ACCENT_SWATCHES,
  BACKGROUND_SWATCHES,
  LOGO_TYPES,
  accentWarning,
  backgroundWarning,
  hexOrNull,
  logoProblem,
} from './branding';

const HEX_HINT = 'Use a 6-digit hex code, like #2B6450.';
const LOGO_ERROR = 'We couldn’t upload the logo. Please try again.';

function ColourPicker({ label, customLabel, hexLabel, swatches, value, onChange, warning }: {
  label: string;
  customLabel: string;
  hexLabel: string;
  swatches: { name: string; hex: string }[];
  value: string;
  onChange: (hex: string) => void;
  warning: string | null;
}) {
  const toast = useToast();
  const labelId = useId();
  const [text, setText] = useState(value);
  useEffect(() => setText(value), [value]);

  function applyText() {
    const hex = hexOrNull(text);
    if (hex) onChange(hex);
    else {
      setText(value);
      toast(HEX_HINT);
    }
  }

  return (
    <div className="edit-field">
      <span id={labelId} className="edit-label">{label}</span>
      <div role="group" aria-labelledby={labelId} className="swatches">
        {swatches.map((swatch) => (
          <button
            key={swatch.hex}
            type="button"
            className="swatch"
            aria-label={swatch.name}
            aria-pressed={value === swatch.hex}
            style={{ background: swatch.hex }}
            onClick={() => onChange(swatch.hex)}
          />
        ))}
        <label className="swatch swatch-custom" title={customLabel}>
          <input
            type="color"
            aria-label={customLabel}
            value={value.toLowerCase()}
            onChange={(event) => onChange(event.target.value.toUpperCase())}
          />
        </label>
        <input
          className="input swatch-hex"
          type="text"
          aria-label={hexLabel}
          maxLength={7}
          value={text}
          onChange={(event) => setText(event.target.value)}
          onBlur={applyText}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault();
              applyText();
            }
          }}
        />
      </div>
      {warning ? <span role="status" className="answer-hint">{warning}</span> : null}
    </div>
  );
}

type Props = {
  survey: Survey;
  accent: string;
  background: string;
  onAccentChange: (hex: string) => void;
  onBackgroundChange: (hex: string) => void;
  /** Called with the survey after its logo was uploaded or removed. */
  onLogoChange: (survey: Survey) => void;
};

/** Logo, accent and background colour. Colours are saved with Save as draft;
 *  the logo is uploaded or removed straight away. */
export function BrandingFields({ survey, accent, background, onAccentChange, onBackgroundChange, onLogoChange }: Props) {
  const toast = useToast();
  const [uploading, setUploading] = useState(false);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  async function upload(file: File) {
    const problem = logoProblem(file);
    if (problem) {
      toast(problem);
      return;
    }
    setUploading(true);
    try {
      const saved = await api.uploadLogo(survey.id, file);
      if (mounted.current) onLogoChange(saved);
    } catch {
      if (mounted.current) toast(LOGO_ERROR);
    } finally {
      if (mounted.current) setUploading(false);
    }
  }

  async function remove() {
    setUploading(true);
    try {
      await api.deleteLogo(survey.id);
      if (mounted.current) onLogoChange({ ...survey, logo_url: null });
    } catch {
      if (mounted.current) toast('We couldn’t remove the logo. Please try again.');
    } finally {
      if (mounted.current) setUploading(false);
    }
  }

  return (
    <div className="branding-fields">
      <div className="branding-logo">
        {survey.logo_url ? (
          <span className="branding-logo-box"><img src={survey.logo_url} alt="Your logo" /></span>
        ) : (
          <span className="branding-logo-box branding-logo-empty">No logo yet</span>
        )}
        <label className={`btn btn-secondary branding-upload${uploading ? ' is-disabled' : ''}`}>
          Upload logo
          <input
            type="file"
            className="visually-hidden"
            accept={LOGO_TYPES.join(',')}
            disabled={uploading}
            onChange={(event) => {
              const file = event.target.files?.[0];
              event.target.value = '';
              if (file) void upload(file);
            }}
          />
        </label>
        {survey.logo_url ? (
          <Button variant="ghost" disabled={uploading} onClick={() => void remove()}>Remove</Button>
        ) : null}
        <span className="answer-hint">PNG, JPG or SVG. A transparent background works best.</span>
      </div>
      <ColourPicker
        label="Accent colour"
        customLabel="Custom colour"
        hexLabel="Hex code"
        swatches={ACCENT_SWATCHES}
        value={accent}
        onChange={onAccentChange}
        warning={accentWarning(accent)}
      />
      <ColourPicker
        label="Background colour"
        customLabel="Custom background colour"
        hexLabel="Background hex code"
        swatches={BACKGROUND_SWATCHES}
        value={background}
        onChange={onBackgroundChange}
        warning={backgroundWarning(background)}
      />
    </div>
  );
}
