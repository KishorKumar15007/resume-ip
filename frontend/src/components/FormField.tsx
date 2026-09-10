import { useId, type ReactNode } from "react";

interface FormFieldProps {
  label: string;
  error?: string;
  help?: string;
  children: (props: { id: string; "aria-describedby"?: string; "aria-invalid": boolean }) => ReactNode;
}

export function FormField({ label, error, help, children }: FormFieldProps) {
  const id = useId();
  const helpId = help ? `${id}-help` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [helpId, errorId].filter(Boolean).join(" ") || undefined;
  return <div className="form-field"><label htmlFor={id}>{label}</label>{children({ id, "aria-describedby": describedBy, "aria-invalid": Boolean(error) })}{help && <p className="field-help" id={helpId}>{help}</p>}{error && <p className="field-error" id={errorId}>{error}</p>}</div>;
}
