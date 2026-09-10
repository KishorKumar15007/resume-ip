import { createContext, useCallback, useEffect, useMemo, useState } from "react";

import { setAuthenticationFailureHandler } from "../api/client";
import type { TokenResponse } from "../api/contracts";
import { isExpired, parseSession, type Session } from "./session";

interface AuthContextValue {
  session: Session | null;
  establishSession: (tokenResponse: TokenResponse) => boolean;
  clearSession: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);

  const clearSession = useCallback(() => setSession(null), []);
  const establishSession = useCallback((tokenResponse: TokenResponse): boolean => {
    if (tokenResponse.token_type !== "bearer") return false;
    const parsed = parseSession(tokenResponse.access_token);
    if (!parsed || isExpired(parsed)) return false;
    setSession(parsed);
    return true;
  }, []);

  useEffect(() => {
    setAuthenticationFailureHandler((token) => {
      setSession((current) => current?.token === token ? null : current);
    });
    return () => setAuthenticationFailureHandler(undefined);
  }, []);

  useEffect(() => {
    if (!session) return;
    const remaining = session.expiresAt - Date.now();
    if (remaining <= 0) {
      clearSession();
      return;
    }
    const timer = window.setTimeout(clearSession, remaining);
    const onFocus = () => { if (isExpired(session)) clearSession(); };
    window.addEventListener("focus", onFocus);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("focus", onFocus);
    };
  }, [clearSession, session]);

  const value = useMemo(() => ({ session, establishSession, clearSession }), [clearSession, establishSession, session]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
