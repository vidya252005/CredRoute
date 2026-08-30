import { useState } from "react";
import { login, setToken, getToken } from "../lib/api.js";

export default function AuthPanel({ onAuthenticated }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    if (!email.trim() || !password) {
      setError("Enter email and password.");
      return;
    }
    setLoading(true);
    try {
      await login(email, password);
      onAuthenticated?.();
    } catch (loginError) {
      setError(loginError.message);
    } finally {
      setLoading(false);
    }
  };

  const signOut = () => {
    setToken(null);
    onAuthenticated?.();
  };

  if (getToken()) {
    return (
      <div className="auth-panel auth-panel--signed-in">
        <p>Signed in as admin</p>
        <button type="button" className="btn btn--secondary" onClick={signOut}>
          Sign out
        </button>
      </div>
    );
  }

  return (
    <form className="auth-panel panel" onSubmit={submit}>
      <h2>Admin sign in</h2>
      <label className="field">
        <span>Email</span>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="admin@credroute.demo"
          required
        />
      </label>
      <label className="field">
        <span>Password</span>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Demo password from README"
          required
        />
      </label>
      {error && <p className="field-error">{error}</p>}
      <button type="submit" className="btn btn--primary" disabled={loading}>
        {loading ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}
