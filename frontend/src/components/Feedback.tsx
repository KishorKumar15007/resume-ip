import type { ReactNode } from "react";

export function Feedback({ children, tone = "info" }: { children: ReactNode; tone?: "error" | "success" | "warning" | "info" }) {
  return <p className={`feedback feedback--${tone}`} role={tone === "error" ? "alert" : "status"}>{children}</p>;
}
