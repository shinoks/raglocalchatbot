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
        <p className="eyebrow">Dostęp Administratora</p>
        <h1>Zarządzaj bazą wiedzy stojącą za każdą odpowiedzią.</h1>
        <p className="muted">
          Przesyłaj pliki, śledź zadania przetwarzania, uruchamiaj ponowne indeksowanie i sprawdzaj, co bot potrafi zacytować.
        </p>
      </div>
      <form className="login-form" onSubmit={handleSubmit}>
        <label>
          <span>E-mail</span>
          <input
            autoComplete="username"
            disabled={disabled}
            onChange={(event) => setEmail(event.target.value)}
            type="email"
            value={email}
          />
        </label>
        <label>
          <span>Hasło</span>
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
          {disabled ? "Logowanie..." : "Zaloguj się"}
        </button>
      </form>
    </section>
  );
}
