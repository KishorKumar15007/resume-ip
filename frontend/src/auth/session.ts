import type { UserRole } from "../api/contracts";

export interface Session {
  token: string;
  userId: string;
  role: UserRole;
  expiresAt: number;
}

function isUserRole(value: unknown): value is UserRole {
  return value === "candidate" || value === "recruiter";
}

export function parseSession(token: string): Session | null {
  const parts = token.split(".");
  if (parts.length !== 3) return null;

  try {
    const payload = JSON.parse(atob(parts[1].replace(/-/g, "+").replace(/_/g, "/"))) as Record<string, unknown>;
    if (typeof payload.sub !== "string" || !isUserRole(payload.role) || typeof payload.exp !== "number") return null;
    return { token, userId: payload.sub, role: payload.role, expiresAt: payload.exp * 1000 };
  } catch {
    return null;
  }
}

export function isExpired(session: Session): boolean {
  return session.expiresAt <= Date.now();
}

export function safeReturnPath(value: string | null): string | null {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return null;
  try {
    const url = new URL(value, window.location.origin);
    if (url.origin !== window.location.origin || url.search || url.hash) return null;
    return url.pathname;
  } catch {
    return null;
  }
}
