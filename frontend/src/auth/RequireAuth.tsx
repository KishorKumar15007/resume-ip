import { useContext } from "react";
import { Navigate, Outlet, useLocation } from "react-router";

import type { UserRole } from "../api/contracts";
import { AuthContext } from "./AuthProvider";

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}

export function RequireAuth({ allowedRoles }: { allowedRoles?: UserRole[] }) {
  const { session } = useAuth();
  const location = useLocation();
  const returnPath = `${location.pathname}${location.search}`;
  if (!session) return <Navigate to={`/login?returnTo=${encodeURIComponent(returnPath)}`} replace />;
  if (allowedRoles && !allowedRoles.includes(session.role)) return <Navigate to="/forbidden" replace />;
  return <Outlet />;
}

export function RedirectIfAuthenticated() {
  const { session } = useAuth();
  return session ? <Navigate to="/session" replace /> : <Outlet />;
}
