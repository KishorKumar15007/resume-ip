import { useEffect } from "react";
import { useLocation } from "react-router";

const titles: Record<string, string> = {
  "/": "Resume Intelligence Portal",
  "/login": "Sign in",
  "/signup": "Create account",
  "/session": "Session",
  "/forbidden": "Access denied",
};

export function RouteEffects() {
  const location = useLocation();
  useEffect(() => {
    document.title = `${titles[location.pathname] ?? "Page not found"} — Resume Intelligence Portal`;
    document.getElementById("main-content")?.focus();
  }, [location.pathname]);
  return null;
}
