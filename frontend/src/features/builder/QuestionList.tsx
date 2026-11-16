import { useEffect, useRef, useState } from 'react';
import { api, type Question, type QuestionInput } from '../../api/client';
import { Button, Card, Checkbox, Select, TextField, useToast } from '../../components/ui';
import { AnswerTypeControls } from './AnswerTypeControls';
import { ANSWER_TYPES, changesForType } from './answerTypes';

// Texts follow the prototype's "Build your survey" screen.
const SAVE_ERROR = 'We couldn’t save your question. Please try again.';
const MANY_QUESTIONS = 5;
/** What "+ Add question" creates, as in the prototype. */
const NEW_QUESTION: QuestionInput = { kind: 'single_choice', prompt: '', options: ['Option 1'], required: false };

type CardProps = {
  question: Question;
  number: number;
  count: number;
  busy: boolean;
  inputRef: (input: HTMLInputElement | null) => void;
  onSavePrompt: (prompt: string) => void;
  onSave: (changes: Partial<QuestionInput>) => void;
  onToggleRequired: () => void;
  onMove: (by: -1 | 1) => void;
  onDuplicate: () => void;
  onDelete: () => void;
};

function QuestionCard({ question, number, count, busy, inputRef, onSavePrompt, onSave, onToggleRequired, onMove, onDuplicate, onDelete }: CardProps) {
  const [text, setText] = useState(question.prompt);
  // Follow the saved text, e.g. after the server trims it or a reload.
  useEffect(() => setText(question.prompt), [question.prompt]);

  return (
    <Card padded className="question-card">
      <div role="group" aria-label={`Question ${number}`} className="question-card-body">
        <div className="question-card-head">
          <TextField
            ref={inputRef}
            label={`Question ${number}`}
            placeholder="Untitled question"
            maxLength={500}
            value={text}
            onChange={(event) => setText(event.target.value)}
            onBlur={() => {
              if (text.trim() !== question.prompt) onSavePrompt(text);
            }}
          />
          <Select
            label="Answer type"
            className="question-type-select"
            options={ANSWER_TYPES}
            value={question.kind}
            disabled={busy}
            onChange={(event) => {
              const kind = event.target.value as Question['kind'];
              if (kind !== question.kind) onSave(changesForType({ ...question, prompt: text }, kind));
            }}
          />
        </div>
        <AnswerTypeControls question={question} number={number} busy={busy} onSaveOptions={(options) => onSave({ options })} />
        <div className="question-actions">
          <Checkbox label="Required" checked={question.required} disabled={busy} onChange={onToggleRequired} />
          <Button variant="ghost" size="sm" aria-label={`Move question ${number} up`} disabled={busy || number === 1} onClick={() => onMove(-1)}>
            ↑
          </Button>
          <Button variant="ghost" size="sm" aria-label={`Move question ${number} down`} disabled={busy || number === count} onClick={() => onMove(1)}>
            ↓
          </Button>
          <Button variant="ghost" size="sm" aria-label={`Duplicate question ${number}`} disabled={busy} onClick={onDuplicate}>
            Duplicate
          </Button>
          <Button variant="ghost" size="sm" aria-label={`Delete question ${number}`} disabled={busy || count <= 1} onClick={onDelete}>
            Delete
          </Button>
        </div>
      </div>
    </Card>
  );
}

/** The survey's questions. Every change is saved right away, one at a time, in order. */
export function QuestionList({ surveyId }: { surveyId: string }) {
  const toast = useToast();
  const [questions, setQuestions] = useState<Question[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [pending, setPending] = useState(0);
  const queue = useRef<Promise<void>>(Promise.resolve());
  const mounted = useRef(true);
  const inputs = useRef(new Map<string, HTMLInputElement>());
  const focusNext = useRef<string | null>(null);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    let active = true;
    setLoadError(false);
    api.questions(surveyId).then(
      (saved) => { if (active) setQuestions(saved); },
      () => { if (active) setLoadError(true); },
    );
    return () => { active = false; };
  }, [surveyId, attempt]);

  // Put the cursor in a question that was just added or duplicated.
  useEffect(() => {
    if (!focusNext.current) return;
    inputs.current.get(focusNext.current)?.focus();
    focusNext.current = null;
  }, [questions]);

  /** Runs saves one after another; on failure, shows an error and reloads what is saved. */
  function save(work: () => Promise<void>) {
    setPending((n) => n + 1);
    queue.current = queue.current
      .then(work)
      .catch(async () => {
        if (!mounted.current) return;
        toast(SAVE_ERROR);
        try {
          const saved = await api.questions(surveyId);
          if (mounted.current) setQuestions(saved);
        } catch {
          if (mounted.current) setLoadError(true);
        }
      })
      .finally(() => { if (mounted.current) setPending((n) => n - 1); });
  }

  const replace = (saved: Question) =>
    setQuestions((list) => list && list.map((q) => (q.id === saved.id ? saved : q)));

  if (loadError) {
    return (
      <div className="survey-error" role="alert">
        <p>We couldn’t load the questions. Please try again.</p>
        <Button onClick={() => setAttempt((n) => n + 1)}>Try again</Button>
      </div>
    );
  }
  if (!questions) return <p role="status">Loading questions…</p>;

  const busy = pending > 0;
  return (
    <section className="question-list" aria-label="Questions">
      {questions.map((question, index) => (
        <QuestionCard
          key={question.id}
          question={question}
          number={index + 1}
          count={questions.length}
          busy={busy}
          inputRef={(input) => {
            if (input) inputs.current.set(question.id, input);
            else inputs.current.delete(question.id);
          }}
          onSavePrompt={(prompt) => save(async () => replace(await api.updateQuestion(surveyId, question.id, { prompt })))}
          onSave={(changes) => {
            replace({ ...question, ...changes });
            save(async () => replace(await api.updateQuestion(surveyId, question.id, changes)));
          }}
          onToggleRequired={() => {
            const required = !question.required;
            replace({ ...question, required });
            save(async () => replace(await api.updateQuestion(surveyId, question.id, { required })));
          }}
          onMove={(by) => {
            const order = questions.map((q) => q.id);
            [order[index], order[index + by]] = [order[index + by], order[index]];
            const byId = new Map(questions.map((q) => [q.id, q]));
            setQuestions(order.map((id) => byId.get(id)!));
            save(async () => setQuestions(await api.reorderQuestions(surveyId, order)));
          }}
          onDuplicate={() => save(async () => {
            const copy = await api.duplicateQuestion(surveyId, question.id);
            focusNext.current = copy.id;
            setQuestions(await api.questions(surveyId));
          })}
          onDelete={() => save(async () => {
            await api.deleteQuestion(surveyId, question.id);
            setQuestions((list) => list && list.filter((q) => q.id !== question.id));
          })}
        />
      ))}
      {questions.length > MANY_QUESTIONS ? (
        <div className="question-warning" role="status">
          You have {questions.length} questions. Surveys with more than 5 questions get noticeably fewer answers.
        </div>
      ) : null}
      <Button
        className="question-add"
        disabled={busy}
        onClick={() => save(async () => {
          const added = await api.addQuestion(surveyId, NEW_QUESTION);
          focusNext.current = added.id;
          setQuestions((list) => (list ? [...list, added] : [added]));
        })}
      >
        + Add question
      </Button>
    </section>
  );
}
