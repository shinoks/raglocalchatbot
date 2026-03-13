import { ChangeEvent, useState } from "react";

type UploadFormProps = {
  busy: boolean;
  onUpload: (file: File) => Promise<void>;
};

export function UploadForm({ busy, onUpload }: UploadFormProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    setSelectedFile(event.target.files?.[0] ?? null);
    setMessage(null);
  }

  async function handleUpload() {
    if (!selectedFile) {
      setMessage("Najpierw wybierz plik PDF, DOCX, DOC lub TXT.");
      return;
    }

    await onUpload(selectedFile);
    setSelectedFile(null);
    setMessage("Przesyłanie zostało dodane do kolejki przetwarzania.");
  }

  return (
    <section className="panel upload-panel">
      <div>
        <p className="eyebrow">Przetwarzanie</p>
        <h2>Dodaj nowe materiały źródłowe do indeksu RAG.</h2>
      </div>
      <div className="upload-controls">
        <label className="file-input">
          <input accept=".pdf,.docx,.doc,.txt" onChange={handleChange} type="file" />
          <span>{selectedFile?.name ?? "Wybierz dokument"}</span>
        </label>
        <button disabled={busy} onClick={handleUpload} type="button">
          {busy ? "Przesyłanie..." : "Prześlij i zindeksuj"}
        </button>
      </div>
      <p className="muted small">Maksymalny rozmiar to 25 MB. PDF-y zawierające tylko obrazy są odrzucane, bo OCR nie jest obsługiwany.</p>
      {message ? <p className="inline-note">{message}</p> : null}
    </section>
  );
}
