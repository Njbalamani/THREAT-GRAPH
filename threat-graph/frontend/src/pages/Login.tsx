import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { ErrorBanner, Notice } from "../components/UI";

export function Login() {
  const { login, user, ready } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("admin@threatgraph.local");
  const [password, setPassword] = useState("ChangeMe123!");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (ready && user) return <Navigate to="/dashboard" replace />;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(username.trim(), password);
      navigate("/dashboard", { replace: true });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-page">
      <section className="login-hero">
        <div className="login-hero__brand">
          <span className="brand__mark">TG</span>
          <strong>THREATGRAPH</strong>
        </div>
        <h1>Map the attack. Connect the evidence. Predict the next move.</h1>
        <p>
          ThreatGraph correlates indicators, events, and intelligence feeds into a real relationship graph, then applies
          machine learning to surface likely escalation paths.
        </p>
        <div className="login-hero__features">
          <div><span>01</span><strong>STIX / TAXII ingestion</strong><small>Import structured intelligence and raw logs.</small></div>
          <div><span>02</span><strong>Graph relationship engine</strong><small>Separate observed links from inferred links.</small></div>
          <div><span>03</span><strong>Advisory ML predictions</strong><small>Prioritize triage without declaring confirmed incidents.</small></div>
        </div>
        <Notice>Model predictions are advisory and must be verified by an analyst.</Notice>
      </section>

      <section className="login-panel">
        <form className="login-card" onSubmit={submit}>
          <span className="login-card__eyebrow">Secure access</span>
          <h2>Sign in to ThreatGraph</h2>
          <p>Use your analyst account to access the investigation workspace.</p>
          <ErrorBanner message={error} onClose={() => setError(null)} />
          <label className="field">
            <span className="field__label">Username or email</span>
            <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" required />
          </label>
          <label className="field">
            <span className="field__label">Password</span>
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required />
          </label>
          <button type="submit" className="button button--primary button--wide" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
          <div className="login-card__hint">
            Local default credentials are pre-filled. Change <code>ADMIN_PASSWORD</code> in <code>.env</code> for real deployments.
          </div>
        </form>
      </section>
    </div>
  );
}
