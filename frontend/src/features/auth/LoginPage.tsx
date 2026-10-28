import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router";

import { ApiError } from "../../api/client";
import { login, verifyMfa } from "../../api/auth";
import { useAuth } from "../../auth/RequireAuth";
import { parseSession, safeReturnPath } from "../../auth/session";
import type { LoginResponse } from "../../api/contracts";
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
  const [mfaToken, setMfaToken] = useState<string>();
  const [mfaCode, setMfaCode] = useState("");
  const [error, setError] = useState<string>();
  const [showValidationErrors, setShowValidationErrors] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const returnPath = safeReturnPath(new URLSearchParams(location.search).get("returnTo"));
  const hasInvalidEmail = !/^\S+@\S+\.\S+$/.test(email);
  const hasInvalidPassword = !password;
  const emailError = showValidationErrors && hasInvalidEmail ? "Enter a valid email address." : undefined;
  const passwordError = showValidationErrors && hasInvalidPassword ? "Enter your password." : undefined;
  const hasInvalidMfaCode = !/^\d{6}$/.test(mfaCode);
  const mfaCodeError = showValidationErrors && hasInvalidMfaCode ? "Enter the six-digit code from your authenticator app." : undefined;

  function isMfaChallenge(response: LoginResponse): response is Extract<LoginResponse, { mfa_required: true }> {
    return "mfa_required" in response && response.mfa_required === true;
  }

  function clearMfaChallenge() {
    setMfaToken(undefined);
    setMfaCode("");
    setShowValidationErrors(false);
  }

  function navigateToWorkspace(accessToken: string, response: Extract<LoginResponse, { access_token: string }>) {
    const session = parseSession(accessToken);
    if (!session || !establishSession(response)) throw new ApiError("authentication");
    navigate(returnPath ?? (session.role === "candidate" ? "/postings" : "/recruiter/postings"), { replace: true });
  }

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(undefined);
    setShowValidationErrors(true);
    if (hasInvalidEmail || hasInvalidPassword) return;
    setIsSubmitting(true);
    try {
      const response = await login({ email, password });
      setPassword("");
      if (isMfaChallenge(response)) {
        setMfaToken(response.mfa_token);
        setShowValidationErrors(false);
        return;
      }
      navigateToWorkspace(response.access_token, response);
    } catch (caught) {
      setError(caught instanceof ApiError && caught.kind === "authentication" ? "Invalid email or password." : "We could not sign you in. Please try again.");
    } finally { setIsSubmitting(false); }
  }

  async function onMfaSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(undefined);
    setShowValidationErrors(true);
    if (!mfaToken || hasInvalidMfaCode) return;
    setIsSubmitting(true);
    let codeVerified = false;
    try {
      const response = await verifyMfa({ mfa_token: mfaToken, code: mfaCode });
      codeVerified = true;
      clearMfaChallenge();
      navigateToWorkspace(response.access_token, response);
    } catch {
      clearMfaChallenge();
      setPassword("");
      setError(codeVerified ? "Your code was verified, but we could not complete sign in. Please sign in again." : "We could not verify that code. Please sign in again.");
    } finally { setIsSubmitting(false); }
  }

  function cancelMfaChallenge() {
    clearMfaChallenge();
    setPassword("");
    setError(undefined);
  }

  if (mfaToken) {
    return <section className="auth-page" aria-labelledby="mfa-login-title"><h1 id="mfa-login-title">Enter your authentication code</h1><p className="lede">Use the current six-digit code from your authenticator app to finish signing in.</p><form className="form" onSubmit={onMfaSubmit} noValidate aria-busy={isSubmitting}>{error && <Feedback tone="error">{error}</Feedback>}<FormField label="Authentication code" error={mfaCodeError}>{(props) => <input {...props} autoComplete="one-time-code" inputMode="numeric" maxLength={6} pattern="[0-9]{6}" value={mfaCode} onChange={(event) => setMfaCode(event.target.value.replace(/\D/g, "").slice(0, 6))} required />}</FormField><div className="session-actions"><Button type="submit" isLoading={isSubmitting}>Verify and sign in</Button><Button type="button" variant="secondary" onClick={cancelMfaChallenge} disabled={isSubmitting}>Back to sign in</Button></div></form></section>;
  }

  return <section className="auth-page" aria-labelledby="login-title"><h1 id="login-title">Sign in</h1><p className="lede">Continue to your resume and hiring workspace.</p><form className="form" onSubmit={onSubmit} noValidate aria-busy={isSubmitting}>{error && <Feedback tone="error">{error}</Feedback>}<FormField label="Email" error={emailError}>{(props) => <input {...props} autoComplete="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />}</FormField><FormField label="Password" error={passwordError}>{(props) => <span className="password-input"><input {...props} autoComplete="current-password" type={showPassword ? "text" : "password"} value={password} onChange={(event) => setPassword(event.target.value)} required /><button className="password-toggle" type="button" aria-controls={props.id} aria-label={showPassword ? "Hide password" : "Show password"} aria-pressed={showPassword} onClick={() => setShowPassword((visible) => !visible)}>{showPassword ? "Hide" : "Show"}</button></span>}</FormField><Button type="submit" isLoading={isSubmitting}>Sign in</Button></form><p className="auth-switch">Need an account? <Link replace to="/signup" state={{ parentPath: "/" }}>Create one</Link>.</p></section>;
}
