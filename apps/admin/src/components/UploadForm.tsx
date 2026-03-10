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
      setMessage("Choose a PDF, DOCX, DOC, or TXT file first.");
      return;
    }

    await onUpload(selectedFile);
    setSelectedFile(null);
    setMessage("Upload queued for ingestion.");
  }

  return (
    <section className="panel upload-panel">
      <div>
        <p className="eyebrow">Ingestion</p>
        <h2>Push new source material into the RAG index.</h2>
      </div>
      <div className="upload-controls">
        <label className="file-input">
          <input accept=".pdf,.docx,.doc,.txt" onChange={handleChange} type="file" />
          <span>{selectedFile?.name ?? "Choose document"}</span>
        </label>
        <button disabled={busy} onClick={handleUpload} type="button">
          {busy ? "Uploading..." : "Upload and index"}
        </button>
      </div>
      <p className="muted small">Max size is 25 MB. Image-only PDFs are rejected because OCR is out of scope.</p>
      {message ? <p className="inline-note">{message}</p> : null}
    </section>
  );
}
