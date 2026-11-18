import { useState, type FormEvent } from 'react';
import { api, errorDetail, type Survey } from '../../api/client';
import { Button, ButtonLink, Card, CardHeader, Checkbox, TextField, useToast } from '../../components/ui';
import { closesAtFromDay, dayFromClosesAt, today } from './closeDate';

const LIMIT_MAX = 1_000_000;

type Form = { day: string; limit: string; notify: boolean };

function formFor(survey: Survey): Form {
  return {
    day: survey.closes_at ? dayFromClosesAt(survey.closes_at) : '',
    limit: survey.response_limit != null ? String(survey.response_limit) : '',
    notify: survey.notify_on_response ?? false,
  };
}

function dayError(day: string): string | null {
  return day !== '' && day < today() ? 'Pick today or a later day.' : null;
}

function limitError(limit: string): string | null {
  if (limit.trim() === '') return null;
  const n = Number(limit);
  return Number.isInteger(n) && n >= 1 && n <= LIMIT_MAX
    ? null
    : `Enter a whole number from 1 to ${LIMIT_MAX.toLocaleString('en')}, or leave it empty.`;
}

/** "Survey settings" on the live page (#48): close date, response limit and "notify me". */
export function SurveySettingsCard({ survey, onSaved }: { survey: Survey; onSaved: (saved: Survey) => void }) {
  const toast = useToast();
  const [saved, setSaved] = useState<Form>(() => formFor(survey));
  const [form, setForm] = useState<Form>(saved);
  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const changed = form.day !== saved.day || form.limit.trim() !== saved.limit || form.notify !== saved.notify;
  const errors = { day: dayError(form.day), limit: limitError(form.limit) };

  async function save(event: FormEvent) {
    event.preventDefault();
    if (errors.day || errors.limit || !changed) return;
    setSaving(true);
    setProblem(null);
    try {
      const updated = await api.updateSurvey(survey.id, {
        closes_at: form.day ? closesAtFromDay(form.day) : null,
        response_limit: form.limit.trim() ? Number(form.limit) : null,
        notify_on_response: form.notify,
      });
      onSaved(updated);
      setSaved(formFor(updated));
      setForm(formFor(updated));
      toast('Settings saved');
    } catch (error) {
      setProblem(errorDetail(error) ?? 'We couldn’t save the settings. Please try again.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card padded className="live-card settings-card">
      <CardHeader title="Survey settings" />
      <form className="settings-form" onSubmit={save} noValidate>
        <div className="settings-row">
          <TextField
            label="Closes on"
            type="date"
            min={today()}
            value={form.day}
            error={errors.day}
            onChange={(e) => setForm({ ...form, day: e.target.value })}
          />
          <TextField
            label="Response limit"
            type="number"
            inputMode="numeric"
            min={1}
            max={LIMIT_MAX}
            step={1}
            placeholder="No limit"
            value={form.limit}
            error={errors.limit}
            onChange={(e) => setForm({ ...form, limit: e.target.value })}
          />
        </div>
        <p className="live-hint">
          The survey takes answers until the end of its last day.
        </p>
        <Checkbox
          label="Notify me of new responses by email"
          checked={form.notify}
          onChange={(e) => setForm({ ...form, notify: e.target.checked })}
        />
        <p className="settings-privacy">
          Answers are anonymous. Readers who tick “Contact me” share their contact so you can follow up.
        </p>
        {problem ? <p className="publish-error" role="alert">{problem}</p> : null}
        <div>
          <Button type="submit" variant="primary" loading={saving} disabled={!changed || saving}>
            Save settings
          </Button>
        </div>
      </form>
      <div className="settings-links">
        <ButtonLink to="/results" variant="secondary">Go to results</ButtonLink>
        <ButtonLink to="/surveys" variant="ghost">Back to all surveys</ButtonLink>
      </div>
    </Card>
  );
}
