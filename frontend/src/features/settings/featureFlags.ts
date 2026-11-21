import { useEffect, useState } from 'react';

/**
 * Feature flags (#153): optional parts of the app each user can turn on or off.
 * Saved per user in this browser (localStorage), not on the server, so other
 * users and devices are not affected. When storage is empty or blocked, every
 * flag has its default. Flags that must follow the user across devices would
 * need a server-side setting instead.
 */
export const FEATURE_FLAGS = {
  newsAndInspiration: {
    label: 'News and inspiration',
    description: 'Show the Recent news and Get inspired articles on the front page.',
    default: false,
  },
} as const;

export type FeatureFlag = keyof typeof FEATURE_FLAGS;

const PREFIX = 'lianasurvey.flag.';
/** Tells other components in this tab that a flag changed (the storage event only reaches other tabs). */
const CHANGED = 'lianasurvey:flag-changed';

export function readFlag(flag: FeatureFlag): boolean {
  try {
    const stored = window.localStorage.getItem(PREFIX + flag);
    if (stored === 'true') return true;
    if (stored === 'false') return false;
  } catch {
    // Storage blocked (private mode, browser settings): use the default.
  }
  return FEATURE_FLAGS[flag].default;
}

/** Saves the choice. Returns false when the browser does not let us store it. */
export function writeFlag(flag: FeatureFlag, on: boolean): boolean {
  let saved = true;
  try {
    window.localStorage.setItem(PREFIX + flag, String(on));
  } catch {
    saved = false;
  }
  window.dispatchEvent(new CustomEvent(CHANGED, { detail: { flag, on } }));
  return saved;
}

/** The flag's value, kept up to date when it changes in this or another tab. */
export function useFeatureFlag(flag: FeatureFlag): [boolean, (on: boolean) => boolean] {
  const [on, setOn] = useState(() => readFlag(flag));
  useEffect(() => {
    const sync = (event: Event) => {
      if (event instanceof CustomEvent && event.detail?.flag === flag) setOn(Boolean(event.detail.on));
      else if (event instanceof StorageEvent && (event.key === null || event.key === PREFIX + flag)) setOn(readFlag(flag));
    };
    window.addEventListener(CHANGED, sync);
    window.addEventListener('storage', sync);
    return () => {
      window.removeEventListener(CHANGED, sync);
      window.removeEventListener('storage', sync);
    };
  }, [flag]);
  return [on, (value: boolean) => writeFlag(flag, value)];
}
