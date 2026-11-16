import { useEffect, useRef, useState } from 'react';
import { api, type Question, type QuestionInput } from '../../api/client';
import { useToast } from '../../components/ui';

export const SAVE_ERROR = 'We couldn’t save your question. Please try again.';

/** A survey's questions, with saves that run one at a time, in order.
 *  A failed save shows an error and reloads what is saved. */
export function useSavedQuestions(surveyId: string) {
  const toast = useToast();
  const [questions, setState] = useState<Question[] | null>(null);
  // The newest list, also between a change and the next render, so a click right
  // after a blur (rename, then remove) works on the renamed options.
  const latest = useRef<Question[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [pending, setPending] = useState(0);
  const queue = useRef<Promise<void>>(Promise.resolve());
  const mounted = useRef(true);

  const setQuestions = (next: Question[] | null | ((list: Question[] | null) => Question[] | null)) => {
    latest.current = typeof next === 'function' ? next(latest.current) : next;
    setState(latest.current);
  };

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

  /** Shows the change at once, then saves it. */
  function update(question: Question, changes: Partial<QuestionInput>) {
    replace({ ...question, ...changes });
    save(async () => replace(await api.updateQuestion(surveyId, question.id, changes)));
  }

  /** Changes a question's options based on its newest options, then saves them. */
  function updateOptions(questionId: string, change: (options: string[]) => string[]) {
    const current = latest.current?.find((q) => q.id === questionId);
    if (current) update(current, { options: change(current.options) });
  }

  return {
    questions,
    setQuestions,
    loadError,
    retry: () => setAttempt((n) => n + 1),
    busy: pending > 0,
    save,
    replace,
    update,
    updateOptions,
  };
}
