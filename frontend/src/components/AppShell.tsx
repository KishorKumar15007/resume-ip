import { Link, NavLink, useLocation } from "react-router";

import { useAuth } from "../auth/RequireAuth";

export function AppShell({ children }: { children: React.ReactNode }) {
  const { session } = useAuth();
  const location = useLocation();
  const isAuthPage = location.pathname === "/login" || location.pathname === "/signup";

  return <><a className="skip-link" href="#main-content">Skip to content</a><header className="app-header"><div className="app-header__content"><Link className="brand" to="/">Resume Intelligence Portal</Link><nav className="nav" aria-label="Primary navigation">{!session && (isAuthPage ? <Link to="/">Back to home</Link> : <><NavLink to="/login">Sign in</NavLink><NavLink to="/signup">Create account</NavLink></>)}</nav></div></header><main className="page" id="main-content" tabIndex={-1}>{children}</main></>;
}
