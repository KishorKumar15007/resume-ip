import { type MouseEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router";

import { useAuth } from "../auth/RequireAuth";

export function AppShell({ children }: { children: React.ReactNode }) {
  const { session } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const isAuthPage = location.pathname === "/login" || location.pathname === "/signup";
  const isCandidateWorkspace = location.pathname === "/postings";
  const isCandidateDetail = /^\/postings\/[^/]+$/.test(location.pathname);
  const isRecruiterWorkspace = location.pathname === "/recruiter/postings";
  const isRecruiterEditor = location.pathname === "/recruiter/postings/new" || /^\/recruiter\/postings\/[^/]+\/edit$/.test(location.pathname);
  const contextualLink = !session
    ? isAuthPage ? { to: "/", label: "Back to home" } : null
    : isCandidateWorkspace ? { to: "/session", label: "Back to session" }
    : isCandidateDetail ? { to: "/postings", label: "Back to postings" }
    : isRecruiterWorkspace ? { to: "/session", label: "Back to session" }
    : isRecruiterEditor ? { to: "/recruiter/postings", label: "Back to postings" }
    : null;

  function returnToParent(event: MouseEvent<HTMLAnchorElement>, parentPath: string) {
    if (event.button !== 0 || event.metaKey || event.altKey || event.ctrlKey || event.shiftKey) return;
    event.preventDefault();
    const state = location.state;
    const cameFromParent = typeof state === "object" && state !== null && "parentPath" in state && state.parentPath === parentPath;
    if (cameFromParent) navigate(-1);
    else navigate(parentPath, { replace: true });
  }

  return <><a className="skip-link" href="#main-content">Skip to content</a><header className="app-header"><div className="app-header__content"><Link className="brand" to="/">Resume Intelligence Portal</Link><nav className="nav" aria-label="Primary navigation">{contextualLink && <Link to={contextualLink.to} onClick={(event) => returnToParent(event, contextualLink.to)}>{contextualLink.label}</Link>}</nav></div></header><main className="page" id="main-content" tabIndex={-1}>{children}</main></>;
}
