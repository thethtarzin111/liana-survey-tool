import { useEffect, useRef, useState } from 'react';

export type CopyState = 'idle' | 'copied' | 'failed';

/** Copies text to the clipboard. The state says "copied" or "failed" for a few seconds. */
export function useCopy(resetMs = 2500): [CopyState, (text: string) => Promise<void>] {
  const [state, setState] = useState<CopyState>('idle');
  const timer = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => () => clearTimeout(timer.current), []);

  async function copy(text: string) {
    clearTimeout(timer.current);
    try {
      await navigator.clipboard.writeText(text);
      setState('copied');
    } catch {
      // No clipboard access (e.g. an http page that isn't localhost): ask to copy by hand.
      setState('failed');
    }
    timer.current = setTimeout(() => setState('idle'), resetMs);
  }

  return [state, copy];
}
