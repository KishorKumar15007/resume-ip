import { useEffect } from "react";
import { useLocation } from "react-router";

const titles: Record<string, string> = {
  "/": "Resume Intelligence Portal",
  "/login": "Sign in",
  "/signup": "Create account",
  "/session": "Session",
  "/postings": "Browse postings",
  "/recruiter/postings": "Your postings",
  "/recruiter/postings/new": "Create posting",
  "/forbidden": "Access denied",
};

export function RouteEffects() {
  const location = useLocation();
  useEffect(() => {
    const title = titles[location.pathname]
      ?? (/^\/postings\/[^/]+$/.test(location.pathname) ? "Posting details"
        : /^\/recruiter\/postings\/[^/]+\/edit$/.test(location.pathname) ? "Edit posting"
        : /^\/recruiter\/postings\/[^/]+\/submissions$/.test(location.pathname) ? "Ranked submissions"
        : "Page not found");
    document.title = location.pathname === "/" ? title : `${title} — Resume Intelligence Portal`;
    document.getElementById("main-content")?.focus();
  }, [location.pathname]);
  return null;
}
