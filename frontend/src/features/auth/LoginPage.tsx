import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router";

import { ApiError } from "../../api/client";
import { login } from "../../api/auth";
import { useAuth } from "../../auth/RequireAuth";
import { safeReturnPath } from "../../auth/session";
import { Button } from "../../components/Button";
import { Feedback } from "../../components/Feedback";
import { FormField } from "../../components/FormField";

export function LoginPage() {
  const { establishSession } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string>();
  const [showValidationErrors, setShowValidationErrors] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const returnPath = safeReturnPath(new URLSearchParams(location.search).get("returnTo"));
  const hasInvalidEmail = !/^\S+@\S+\.\S+$/.test(email);
  const hasInvalidPassword = !password;
  const emailError = showValidationErrors && hasInvalidEmail ? "Enter a valid email address." : undefined;
  const passwordError = showValidationErrors && hasInvalidPassword ? "Enter your password." : undefined;

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(undefined);
    setShowValidationErrors(true);
    if (hasInvalidEmail || hasInvalidPassword) return;
    setIsSubmitting(true);
    try {
      const response = await login({ email, password });
      if (!establishSession(response)) throw new ApiError("authentication");
      setPassword("");
      navigate(returnPath ?? "/session", { replace: true });
    } catch (caught) {
      setError(caught instanceof ApiError && caught.kind === "authentication" ? "Invalid email or password." : "We could not sign you in. Please try again.");
    } finally { setIsSubmitting(false); }
  }

  return <section className="auth-page" aria-labelledby="login-title"><h1 id="login-title">Sign in</h1><p className="lede">Continue to your resume and hiring workspace.</p><form className="form" onSubmit={onSubmit} noValidate aria-busy={isSubmitting}>{error && <Feedback tone="error">{error}</Feedback>}<FormField label="Email" error={emailError}>{(props) => <input {...props} autoComplete="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />}</FormField><FormField label="Password" error={passwordError}>{(props) => <span className="password-input"><input {...props} autoComplete="current-password" type={showPassword ? "text" : "password"} value={password} onChange={(event) => setPassword(event.target.value)} required /><button className="password-toggle" type="button" aria-controls={props.id} aria-label={showPassword ? "Hide password" : "Show password"} aria-pressed={showPassword} onClick={() => setShowPassword((visible) => !visible)}>{showPassword ? "Hide" : "Show"}</button></span>}</FormField><Button type="submit" isLoading={isSubmitting}>Sign in</Button></form><p className="auth-switch">Need an account? <Link to="/signup">Create one</Link>.</p></section>;
}
