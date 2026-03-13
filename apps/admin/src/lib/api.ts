export type AdminUser = {
  id: string;
  email: string;
  created_at: string;
};

export type DocumentItem = {
  id: string;
  filename: string;
  checksum: string;
  format: string;
  status: "processing" | "ready" | "failed";
  chunk_count: number;
  last_indexed_at: string | null;
  uploaded_at: string;
  error_message: string | null;
};

export type Citation = {
  document_id: string;
  filename: string;
  page: number | null;
  section: string | null;
  excerpt: string;
};

export type IngestionJob = {
  id: string;
  document_id: string;
  job_type: string;
  status: string;
  error_message: string | null;
  queue_job_id: string | null;
  enqueued_at: string;
  started_at: string | null;
  finished_at: string | null;
};

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    credentials: "include",
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(init?.headers ?? {}),
    },
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  const data = text ? JSON.parse(text) : undefined;
  if (!response.ok) {
    throw new ApiError(data?.detail ?? "Żądanie nie powiodło się.", response.status);
  }

  return data as T;
}

export async function fetchMe(): Promise<AdminUser> {
  return request<AdminUser>("/api/admin/me");
}

export async function login(email: string, password: string): Promise<AdminUser> {
  return request<AdminUser>("/api/admin/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function logout(): Promise<void> {
  return request<void>("/api/admin/logout", { method: "POST" });
}

export async function fetchDocuments(): Promise<DocumentItem[]> {
  return request<DocumentItem[]>("/api/admin/documents");
}

export async function uploadDocument(file: File): Promise<DocumentItem> {
  const formData = new FormData();
  formData.append("file", file);
  return request<DocumentItem>("/api/admin/documents", {
    method: "POST",
    body: formData,
  });
}

export async function reindexDocument(documentId: string): Promise<IngestionJob> {
  return request<IngestionJob>(`/api/admin/documents/${documentId}/reindex`, {
    method: "POST",
  });
}

export async function deleteDocument(documentId: string): Promise<void> {
  return request<void>(`/api/admin/documents/${documentId}`, {
    method: "DELETE",
  });
}

export async function fetchCitations(documentId: string): Promise<Citation[]> {
  return request<Citation[]>(`/api/admin/documents/${documentId}/citations`);
}

export { ApiError, apiBaseUrl };
