import { FormEvent, useState } from "react";

type LoginFormProps = {
  disabled: boolean;
  error: string | null;
  onSubmit: (email: string, password: string) => Promise<void>;
};

export function LoginForm({ disabled, error, onSubmit }: LoginFormProps) {
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("change-me");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSubmit(email, password);
  }

  return (
    <section className="login-card">
      <div>
        <p className="eyebrow">Admin Access</p>
        <h1>Control the knowledge base behind every answer.</h1>
        <p className="muted">
          Upload files, watch ingestion jobs, reindex documents, and verify what the bot can cite.
        </p>
      </div>
      <form className="login-form" onSubmit={handleSubmit}>
        <label>
          <span>Email</span>
          <input
            autoComplete="username"
            disabled={disabled}
            onChange={(event) => setEmail(event.target.value)}
            type="email"
            value={email}
          />
        </label>
        <label>
          <span>Password</span>
          <input
            autoComplete="current-password"
            disabled={disabled}
            onChange={(event) => setPassword(event.target.value)}
            type="password"
            value={password}
          />
        </label>
        {error ? <p className="form-error">{error}</p> : null}
        <button disabled={disabled} type="submit">
          {disabled ? "Signing in..." : "Sign in"}
        </button>
      </form>
    </section>
  );
}
