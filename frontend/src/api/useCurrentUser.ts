import { useEffect, useState } from 'react';
import { api, type CurrentUser } from './client';

/** The demo user from the dev-auth stub. null while loading or if the API is down. */
export function useCurrentUser(): CurrentUser | null {
  const [user, setUser] = useState<CurrentUser | null>(null);
  useEffect(() => {
    let alive = true;
    api
      .me()
      .then((u) => {
        if (alive) setUser(u);
      })
      .catch(() => {
        if (alive) setUser(null);
      });
    return () => {
      alive = false;
    };
  }, []);
  return user;
}
