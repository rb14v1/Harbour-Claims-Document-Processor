import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext";
import { ApiError } from "../api";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("adjuster@claims.demo");
  const [password, setPassword] = useState("Password123!");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      navigate("/claims");
    } catch (err) {
      if (err instanceof ApiError) {
        setError("Login failed: invalid email or password.");
      } else {
        setError("Login failed: could not reach the server.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-shell">
      <div className="card">
        <h1>Claims Document Processor</h1>
        <p className="muted">Sign in to review and process insurance claims.</p>
        {error && <div className="error-banner">{error}</div>}
        <form className="form-grid" onSubmit={handleSubmit}>
          <label>
            Email
            <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
          </label>
          <label>
            Password
            <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" required />
          </label>
          <button type="submit" disabled={submitting}>
            {submitting ? "Signing in..." : "Sign in"}
          </button>
        </form>
        <p className="muted" style={{ marginTop: "1rem" }}>
          Demo logins: adjuster@claims.demo / admin@claims.demo, password Password123!
        </p>
      </div>
    </div>
  );
}
