import { useState } from "react";
import { useNavigate } from "react-router";
import { QRCodeSVG } from "qrcode.react";

import { confirmMfa, setupMfa } from "../../api/auth";
import { ApiError } from "../../api/client";
import { useAuth } from "../../auth/RequireAuth";
import { Button } from "../../components/Button";
import { Feedback } from "../../components/Feedback";
import { FormField } from "../../components/FormField";

function manualKeyFromProvisioningUri(provisioningUri: string): string | null {
  try {
    const uri = new URL(provisioningUri);
    if (uri.protocol !== "otpauth:" || uri.hostname !== "totp") return null;
    const secret = uri.searchParams.get("secret");
    return secret && /^[A-Z2-7]+$/.test(secret) ? secret : null;
  } catch {
    return null;
  }
}

export function MfaSetupPage() {
  const { establishSession, session } = useAuth();
  const navigate = useNavigate();
  const [provisioningUri, setProvisioningUri] = useState<string>();
  const [manualKey, setManualKey] = useState<string>();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string>();
  const [showValidationErrors, setShowValidationErrors] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [sessionRefreshFailed, setSessionRefreshFailed] = useState(false);
  const hasInvalidCode = !/^\d{6}$/.test(code);
  const codeError = showValidationErrors && hasInvalidCode ? "Enter the six-digit code from your authenticator app." : undefined;

  function clearEnrollment() {
    setProvisioningUri(undefined);
    setManualKey(undefined);
    setCode("");
    setShowValidationErrors(false);
  }

  function cancelEnrollment() {
    clearEnrollment();
    setError(undefined);
    navigate("/session", { replace: true });
  }

  async function startEnrollment() {
    if (!session) return;
    setError(undefined);
    clearEnrollment();
    setIsSubmitting(true);
    try {
      const response = await setupMfa(session.token);
      const key = manualKeyFromProvisioningUri(response.provisioning_uri);
      if (!key) throw new ApiError("unexpected");
      setProvisioningUri(response.provisioning_uri);
      setManualKey(key);
    } catch {
      clearEnrollment();
      setError("We could not start MFA setup. Please try again.");
    } finally { setIsSubmitting(false); }
  }

  async function confirmEnrollment(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(undefined);
    setShowValidationErrors(true);
    if (!session || hasInvalidCode) return;
    setIsSubmitting(true);
    try {
      const response = await confirmMfa(session.token, { code });
      clearEnrollment();
      if (!establishSession(response)) setSessionRefreshFailed(true);
      setIsComplete(true);
    } catch {
      clearEnrollment();
      setError("We could not confirm that code. Start setup again and try a current code.");
    } finally { setIsSubmitting(false); }
  }

  if (isComplete) {
    return <section className="auth-page" aria-labelledby="mfa-complete-title"><h1 id="mfa-complete-title">MFA is enabled</h1><Feedback tone="success">Your authenticator app can now be used when you sign in.</Feedback>{sessionRefreshFailed && <Feedback tone="warning">MFA was confirmed, but we could not refresh your session. Sign out and sign in again before continuing.</Feedback>}<div className="session-actions"><Button type="button" onClick={() => navigate("/session", { replace: true })}>Return to your session</Button></div></section>;
  }

  return <section className="auth-page" aria-labelledby="mfa-setup-title"><p className="eyebrow">Account security</p><h1 id="mfa-setup-title">Set up MFA</h1><p className="lede">Add this account to your authenticator app, then confirm a current six-digit code.</p>{error && <Feedback tone="error">{error}</Feedback>}{!provisioningUri || !manualKey ? <div className="form"><Button type="button" onClick={() => void startEnrollment()} isLoading={isSubmitting}>Start MFA setup</Button><Button type="button" variant="secondary" onClick={cancelEnrollment} disabled={isSubmitting}>Cancel</Button></div> : <><div className="form"><QRCodeSVG value={provisioningUri} size={192} level="M" marginSize={4} title="Authenticator setup QR code" /><p className="field-help">If you cannot scan the code, enter this setup key in your authenticator app.</p><code>{manualKey}</code></div><form className="form" onSubmit={confirmEnrollment} noValidate aria-busy={isSubmitting}><FormField label="Authentication code" error={codeError}>{(props) => <input {...props} autoComplete="one-time-code" inputMode="numeric" maxLength={6} pattern="[0-9]{6}" value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))} required />}</FormField><div className="session-actions"><Button type="submit" isLoading={isSubmitting}>Confirm MFA</Button><Button type="button" variant="secondary" onClick={cancelEnrollment} disabled={isSubmitting}>Cancel</Button></div></form></>}</section>;
}
