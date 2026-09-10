import { Link } from "react-router";

import { Button } from "../../components/Button";
import { useAuth } from "../../auth/RequireAuth";

export function SessionPage() {
  const { clearSession, session } = useAuth();
  if (!session) return null;
  const expiresAt = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(session.expiresAt);
  return <section className="auth-page session-page" aria-labelledby="session-title"><p className="eyebrow">Account</p><h1 id="session-title">Your session</h1><p className="lede">You are signed in and ready for the portal’s hiring workflow.</p><dl className="session-details"><div><dt>Role</dt><dd>{session.role === "candidate" ? "Candidate" : "Recruiter"}</dd></div><div><dt>Session expires</dt><dd>{expiresAt}</dd></div></dl><p className="session-note">For your privacy, this session is kept only in this browser page and ends after a reload or when it expires.</p><div className="session-actions"><Link className="button button--secondary" to="/">Back to home</Link><Button type="button" variant="secondary" onClick={clearSession}>Sign out</Button></div></section>;
}
