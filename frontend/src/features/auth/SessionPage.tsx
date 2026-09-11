import { Link, useNavigate } from "react-router";

import { Button } from "../../components/Button";
import { useAuth } from "../../auth/RequireAuth";

export function SessionPage() {
  const { clearSession, session } = useAuth();
  const navigate = useNavigate();
  if (!session) return null;
  const expiresAt = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(session.expiresAt);
  const workspace = session.role === "candidate"
    ? { to: "/postings", label: "Browse postings" }
    : { to: "/recruiter/postings", label: "Your postings" };
  function signOut() {
    clearSession();
    navigate("/", { replace: true });
  }

  return <section className="auth-page session-page" aria-labelledby="session-title"><p className="eyebrow">Account</p><h1 id="session-title">Your session</h1><p className="lede">You are signed in and ready for the portal’s hiring workflow.</p><dl className="session-details"><div><dt>Role</dt><dd>{session.role === "candidate" ? "Candidate" : "Recruiter"}</dd></div><div><dt>Session expires</dt><dd>{expiresAt}</dd></div></dl><p className="session-note">This session stays in memory only and ends after a reload or when it expires.</p><div className="session-actions"><Link className="button button--primary" to={workspace.to} state={{ parentPath: "/session" }}>{workspace.label}</Link><Button type="button" variant="secondary" onClick={signOut}>Sign out</Button></div></section>;
}
