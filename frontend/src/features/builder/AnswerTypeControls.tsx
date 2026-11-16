import { useEffect, useState } from 'react';
import type { Question } from '../../api/client';
import { Button, IconButton, icons } from '../../components/ui';
import { CHOICE_KINDS, MAX_OPTIONS, REASONS_HINT, SCALES, TEXT_HINTS, newOptionText } from './answerTypes';

type Props = {
  question: Question;
  number: number;
  /** Changes the options, starting from the newest saved ones. */
  onChangeOptions: (change: (options: string[]) => string[]) => void;
  /** How screen readers name the question, e.g. "Extra question 1". Defaults to "Question N". */
  name?: string;
};

function OptionRow({ question, name, index, onSave, onRemove }: {
  question: Question;
  name: string;
  index: number;
  onSave: (text: string) => void;
  onRemove: () => void;
}) {
  const saved = question.options[index];
  const [text, setText] = useState(saved);
  useEffect(() => setText(saved), [saved]);
  const mark = question.kind === 'dropdown' ? String(index + 1) : '';

  return (
    <div className="option-row">
      <span className={`option-mark option-mark-${question.kind}`} aria-hidden="true">{mark}</span>
      <input
        className="input"
        type="text"
        aria-label={`${name}, option ${index + 1}`}
        maxLength={200}
        value={text}
        onChange={(event) => setText(event.target.value)}
        onBlur={() => {
          // An emptied option goes back to its saved text; options cannot be blank.
          if (!text.trim()) setText(saved);
          else if (text.trim() !== saved) onSave(text.trim());
        }}
      />
      <IconButton
        label={`Remove option ${index + 1}`}
        icon={icons.close}
        iconSize={14}
        disabled={question.options.length <= 1}
        onClick={onRemove}
      />
    </div>
  );
}

/** The part of a question card that depends on its answer type. */
export function AnswerTypeControls({ question, number, onChangeOptions, name = `Question ${number}` }: Props) {
  const { kind, options } = question;

  if (CHOICE_KINDS.has(kind)) {
    return (
      <div className="answer-options">
        {options.map((_, index) => (
          <OptionRow
            key={`${question.id}-${index}`}
            question={question}
            name={name}
            index={index}
            onSave={(text) => onChangeOptions((current) => current.map((o, i) => (i === index ? text : o)))}
            onRemove={() => onChangeOptions((current) => current.filter((_, i) => i !== index))}
          />
        ))}
        <Button
          variant="ghost"
          size="sm"
          className="answer-add-option"
          disabled={options.length >= MAX_OPTIONS}
          onClick={() => onChangeOptions((current) => [...current, newOptionText(kind, current)])}
        >
          {kind === 'reasons' ? '+ Add reason' : '+ Add option'}
        </Button>
        {kind === 'reasons' ? <span className="answer-hint">{REASONS_HINT}</span> : null}
      </div>
    );
  }

  const scale = SCALES[kind];
  if (scale) {
    return (
      <div className="answer-scale">
        <div className={`answer-scale-numbers answer-scale-${kind}`} aria-hidden="true">
          {scale.numbers.map((n) => <span key={n}>{n}</span>)}
        </div>
        <span className="answer-hint">{scale.hint}</span>
      </div>
    );
  }

  return (
    <div className={`answer-text-preview answer-text-${kind}`}>
      {TEXT_HINTS[kind]}
    </div>
  );
}
