import { startTransition, useEffect, useMemo, useState } from "react";

import { DocumentTable } from "./components/DocumentTable";
import { LoginForm } from "./components/LoginForm";
import { UploadForm } from "./components/UploadForm";
import {
  AdminUser,
  ApiError,
  Citation,
  DocumentItem,
  fetchCitations,
  fetchDocuments,
  fetchMe,
  login,
  logout,
  reindexDocument,
  deleteDocument as removeDocument,
  uploadDocument,
} from "./lib/api";

const REFRESH_INTERVAL_MS = 5000;

export default function App() {
  const [admin, setAdmin] = useState<AdminUser | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [citationDocumentId, setCitationDocumentId] = useState<string | null>(null);
  const [busyDocumentId, setBusyDocumentId] = useState<string | null>(null);
  const [booting, setBooting] = useState(true);
  const [authBusy, setAuthBusy] = useState(false);
  const [uploadBusy, setUploadBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refreshDocuments() {
    const nextDocuments = await fetchDocuments();
    startTransition(() => {
      setDocuments(nextDocuments);
    });
  }

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      try {
        const currentAdmin = await fetchMe();
        if (!cancelled) {
          setAdmin(currentAdmin);
          await refreshDocuments();
        }
      } catch {
        if (!cancelled) {
          setAdmin(null);
        }
      } finally {
        if (!cancelled) {
          setBooting(false);
        }
      }
    }

    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!admin) {
      return;
    }

    const handle = window.setInterval(() => {
      void refreshDocuments();
    }, REFRESH_INTERVAL_MS);

    return () => {
      window.clearInterval(handle);
    };
  }, [admin]);

  const processingCount = useMemo(
    () => documents.filter((document) => document.status === "processing").length,
    [documents],
  );

  async function handleLogin(email: string, password: string) {
    setAuthBusy(true);
    setError(null);
    try {
      const currentAdmin = await login(email, password);
      setAdmin(currentAdmin);
      await refreshDocuments();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Nie udało się zalogować.");
    } finally {
      setAuthBusy(false);
    }
  }

  async function handleLogout() {
    await logout();
    setAdmin(null);
    setDocuments([]);
    setCitations([]);
    setCitationDocumentId(null);
  }

  async function handleUpload(file: File) {
    setUploadBusy(true);
    setError(null);
    try {
      await uploadDocument(file);
      await refreshDocuments();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Przesyłanie nie powiodło się.");
    } finally {
      setUploadBusy(false);
    }
  }

  async function handleReindex(documentId: string) {
    setBusyDocumentId(documentId);
    setError(null);
    try {
      await reindexDocument(documentId);
      await refreshDocuments();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ponowne indeksowanie nie powiodło się.");
    } finally {
      setBusyDocumentId(null);
    }
  }

  async function handleDelete(documentId: string) {
    setBusyDocumentId(documentId);
    setError(null);
    try {
      await removeDocument(documentId);
      setCitations([]);
      setCitationDocumentId((current) => (current === documentId ? null : current));
      await refreshDocuments();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Usuwanie nie powiodło się.");
    } finally {
      setBusyDocumentId(null);
    }
  }

  async function handlePreview(documentId: string) {
    setBusyDocumentId(documentId);
    setError(null);
    try {
      const nextCitations = await fetchCitations(documentId);
      setCitations(nextCitations);
      setCitationDocumentId(documentId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Nie udało się wczytać cytowań.");
    } finally {
      setBusyDocumentId(null);
    }
  }

  if (booting) {
    return <main className="shell loading-state">Sprawdzanie sesji administratora…</main>;
  }

  if (!admin) {
    return (
      <main className="shell login-shell">
        <LoginForm disabled={authBusy} error={error} onSubmit={handleLogin} />
      </main>
    );
  }

  return (
    <main className="shell">
      <header className="hero panel">
        <div>
          <p className="eyebrow">Panel Sterowania RAG</p>
          <h1>Dbaj o trafność chatbota, zarządzając tym, co może wyszukiwać.</h1>
          <p className="muted">
            Zalogowano jako <strong>{admin.email}</strong>. Obecnie indeksuje się {processingCount} dokumentów.
          </p>
        </div>
        <button className="ghost" onClick={handleLogout} type="button">
          Wyloguj
        </button>
      </header>

      {error ? <p className="form-error banner-error">{error}</p> : null}

      <section className="dashboard-grid">
        <UploadForm busy={uploadBusy} onUpload={handleUpload} />
        <section className="panel stats-panel">
          <p className="eyebrow">Stan Systemu</p>
          <div className="stats-grid">
            <article>
              <strong>{documents.length}</strong>
              <span>dokumentów w systemie</span>
            </article>
            <article>
              <strong>{documents.filter((document) => document.status === "ready").length}</strong>
              <span>gotowych do wyszukiwania</span>
            </article>
            <article>
              <strong>{documents.filter((document) => document.status === "failed").length}</strong>
              <span>wymaga uwagi</span>
            </article>
          </div>
        </section>
      </section>

      <DocumentTable
        busyDocumentId={busyDocumentId}
        citationDocumentId={citationDocumentId}
        citations={citations}
        documents={documents}
        onDelete={handleDelete}
        onPreview={handlePreview}
        onReindex={handleReindex}
      />
    </main>
  );
}
