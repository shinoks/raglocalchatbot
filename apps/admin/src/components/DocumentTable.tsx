import { Citation, DocumentItem } from "../lib/api";

type DocumentTableProps = {
  busyDocumentId: string | null;
  citations: Citation[];
  citationDocumentId: string | null;
  documents: DocumentItem[];
  onDelete: (documentId: string) => Promise<void>;
  onPreview: (documentId: string) => Promise<void>;
  onReindex: (documentId: string) => Promise<void>;
};

function formatDate(value: string | null) {
  if (!value) {
    return "Nigdy";
  }
  return new Date(value).toLocaleString();
}

function statusLabel(status: DocumentItem["status"]) {
  switch (status) {
    case "processing":
      return "przetwarzanie";
    case "ready":
      return "gotowy";
    case "failed":
      return "błąd";
    default:
      return status;
  }
}

export function DocumentTable({
  busyDocumentId,
  citations,
  citationDocumentId,
  documents,
  onDelete,
  onPreview,
  onReindex,
}: DocumentTableProps) {
  return (
    <section className="panel table-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Baza Wiedzy</p>
          <h2>Przesłane dokumenty</h2>
        </div>
        <span className="badge">Łącznie: {documents.length}</span>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Nazwa</th>
              <th>Status</th>
              <th>Format</th>
              <th>Chunki</th>
              <th>Zindeksowano</th>
              <th>Akcje</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((document) => {
              const busy = busyDocumentId === document.id;
              const isCitationOpen = citationDocumentId === document.id;
              return (
                <tr key={document.id}>
                  <td>
                    <strong>{document.filename}</strong>
                    <p className="table-subtext">Przesłano {formatDate(document.uploaded_at)}</p>
                    {document.error_message ? <p className="form-error">{document.error_message}</p> : null}
                  </td>
                  <td>
                    <span className={`status-pill status-${document.status}`}>{statusLabel(document.status)}</span>
                  </td>
                  <td>{document.format.toUpperCase()}</td>
                  <td>{document.chunk_count}</td>
                  <td>{formatDate(document.last_indexed_at)}</td>
                  <td>
                    <div className="table-actions">
                      <button disabled={busy} onClick={() => onPreview(document.id)} type="button">
                        {isCitationOpen ? "Odśwież cytowania" : "Pokaż cytowania"}
                      </button>
                      <button disabled={busy} onClick={() => onReindex(document.id)} type="button">
                        Indeksuj ponownie
                      </button>
                      <button className="danger" disabled={busy} onClick={() => onDelete(document.id)} type="button">
                        Usuń
                      </button>
                    </div>
                    {isCitationOpen ? (
                      <div className="citation-drawer">
                        {citations.length === 0 ? (
                          <p className="muted small">Brak dostępnych cytowań.</p>
                        ) : (
                          citations.map((citation, index) => (
                            <article className="citation-card" key={`${citation.document_id}-${index}`}>
                              <header>
                                <strong>{citation.filename}</strong>
                                <span>
                                  {citation.page ? `Strona ${citation.page}` : citation.section ?? "Fragment dokumentu"}
                                </span>
                              </header>
                              <p>{citation.excerpt}</p>
                            </article>
                          ))
                        )}
                      </div>
                    ) : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
