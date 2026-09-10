import { Link } from "react-router";

export function ForbiddenPage() {
  return <section className="auth-page" aria-labelledby="forbidden-title"><h1 id="forbidden-title">Access denied</h1><p className="lede">Your account does not have access to this page.</p><p><Link to="/session">Return to your session</Link></p></section>;
}
