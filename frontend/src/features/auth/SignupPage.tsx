import { useState } from "react";
import { Link, useNavigate } from "react-router";

import { signup } from "../../api/auth";
import { ApiError } from "../../api/client";
import type { UserRole } from "../../api/contracts";
import { useAuth } from "../../auth/RequireAuth";
import { Button } from "../../components/Button";
import { Feedback } from "../../components/Feedback";
import { FormField } from "../../components/FormField";

export function SignupPage() {
  const { establishSession } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [role, setRole] = useState<UserRole>("candidate");
  const [error, setError] = useState<string>();
  const [showValidationErrors, setShowValidationErrors] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const hasInvalidEmail = !/^\S+@\S+\.\S+$/.test(email);
  const hasInvalidPassword = password.length < 8;
  const emailError = showValidationErrors && hasInvalidEmail ? "Enter a valid email address." : undefined;
  const passwordError = showValidationErrors && hasInvalidPassword ? "Use at least 8 characters." : undefined;

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(undefined);
    setShowValidationErrors(true);
    if (hasInvalidEmail || hasInvalidPassword) return;
    setIsSubmitting(true);
    try {
      const response = await signup({ email, password, role });
      if (!establishSession(response)) throw new ApiError("authentication");
      setPassword("");
      navigate("/session", { replace: true });
    } catch (caught) {
      setError(caught instanceof ApiError && caught.kind === "conflict" ? "An account already exists for this email address." : caught instanceof ApiError && caught.kind === "validation" ? "Please review your account details and try again." : "We could not create your account. Please try again.");
    } finally { setIsSubmitting(false); }
  }

  return <section className="auth-page" aria-labelledby="signup-title"><h1 id="signup-title">Create account</h1><p className="lede">Choose the role that matches how you will use the portal.</p><form className="form" onSubmit={onSubmit} noValidate aria-busy={isSubmitting}>{error && <Feedback tone="error">{error}</Feedback>}<FormField label="Email" error={emailError}>{(props) => <input {...props} autoComplete="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />}</FormField><FormField label="Password" error={passwordError} help="Use at least 8 characters.">{(props) => <span className="password-input"><input {...props} autoComplete="new-password" minLength={8} type={showPassword ? "text" : "password"} value={password} onChange={(event) => setPassword(event.target.value)} required /><button className="password-toggle" type="button" aria-controls={props.id} aria-label={showPassword ? "Hide password" : "Show password"} aria-pressed={showPassword} onClick={() => setShowPassword((visible) => !visible)}>{showPassword ? "Hide" : "Show"}</button></span>}</FormField><FormField label="Role">{(props) => <select {...props} value={role} onChange={(event) => setRole(event.target.value as UserRole)}><option value="candidate">Candidate</option><option value="recruiter">Recruiter</option></select>}</FormField><Button type="submit" isLoading={isSubmitting}>Create account</Button></form><p className="auth-switch">Already have an account? <Link to="/login">Sign in</Link>.</p></section>;
}
