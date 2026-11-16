import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';

/** How long a toast stays, like the prototype. */
export const TOAST_MS = 2600;

type ToastFn = (message: string) => void;

const ToastContext = createContext<ToastFn | null>(null);

/**
 * Wrap the app once. Toasts are short confirmations ("Copied", "Survey saved").
 * The region is always in the page with role="status", so screen readers
 * announce each new message without moving focus.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState('');
  const [key, setKey] = useState(0);
  const timer = useRef<ReturnType<typeof setTimeout>>();

  const show = useCallback<ToastFn>((msg) => {
    clearTimeout(timer.current);
    setMessage(msg);
    setKey((k) => k + 1); // restart the animation for repeated messages
    timer.current = setTimeout(() => setMessage(''), TOAST_MS);
  }, []);

  useEffect(() => () => clearTimeout(timer.current), []);

  return (
    <ToastContext.Provider value={show}>
      {children}
      <div className="toast-region" role="status" aria-live="polite">
        {message ? (
          <div key={key} className="toast">
            {message}
          </div>
        ) : null}
      </div>
    </ToastContext.Provider>
  );
}

/** const toast = useToast(); toast('Survey saved'); */
export function useToast(): ToastFn {
  const fn = useContext(ToastContext);
  if (!fn) throw new Error('useToast() needs <ToastProvider> around the app');
  return fn;
}
