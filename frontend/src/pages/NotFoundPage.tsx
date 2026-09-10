import { Link } from "react-router";

export function NotFoundPage() {
  return <section className="auth-page" aria-labelledby="not-found-title"><h1 id="not-found-title">Page not found</h1><p className="lede">The page you requested is not available.</p><p><Link to="/">Return to the portal</Link></p></section>;
}
