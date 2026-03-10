import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

type Citation = {
  document_id: string;
  filename: string;
  page: number | null;
  section: string | null;
  excerpt: string;
};

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  status?: string;
};

type WidgetAppProps = {
  apiBaseUrl: string;
  inline?: boolean;
  siteKey: string;
  title?: string;
};

type StoredWidgetState = {
  messages: ChatMessage[];
  sessionId: string | null;
};

class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function storageKey(apiBaseUrl: string, siteKey: string) {
  return `rag-widget:${apiBaseUrl}:${siteKey}`;
}

function createId() {
  return Math.random().toString(36).slice(2, 10);
}

function loadState(apiBaseUrl: string, siteKey: string): StoredWidgetState {
  try {
    const raw = window.localStorage.getItem(storageKey(apiBaseUrl, siteKey));
    if (!raw) {
      return { messages: [], sessionId: null };
    }
    return JSON.parse(raw) as StoredWidgetState;
  } catch {
    return { messages: [], sessionId: null };
  }
}

async function createSession(apiBaseUrl: string, siteKey: string) {
  const response = await fetch(`${apiBaseUrl}/api/chat/sessions`, {
    method: "POST",
    headers: {
      "X-Site-Key": siteKey,
    },
  });

  const payload = await response.json();
  if (!response.ok) {
    throw new ApiError(response.status, payload?.detail ?? "Could not create chat session.");
  }

  return payload.session_id as string;
}

async function sendMessage(apiBaseUrl: string, siteKey: string, sessionId: string, message: string) {
  const response = await fetch(`${apiBaseUrl}/api/chat/messages`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Site-Key": siteKey,
    },
    body: JSON.stringify({ session_id: sessionId, message }),
  });

  const payload = await response.json();
  if (!response.ok) {
    throw new ApiError(response.status, payload?.detail ?? "Chat request failed.");
  }

  return payload as {
    answer: string;
    citations: Citation[];
    session_id: string;
    status: string;
  };
}

export function WidgetApp({ apiBaseUrl, inline = false, siteKey, title = "Ask the docs" }: WidgetAppProps) {
  const initialState = useMemo(() => loadState(apiBaseUrl, siteKey), [apiBaseUrl, siteKey]);
  const [open, setOpen] = useState(inline);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>(initialState.messages);
  const [sessionId, setSessionId] = useState<string | null>(initialState.sessionId);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    window.localStorage.setItem(
      storageKey(apiBaseUrl, siteKey),
      JSON.stringify({ sessionId, messages }),
    );
  }, [apiBaseUrl, messages, sessionId, siteKey]);

  useEffect(() => {
    if (sessionId) {
      return;
    }

    let cancelled = false;
    void createSession(apiBaseUrl, siteKey)
      .then((nextSessionId) => {
        if (!cancelled) {
          setSessionId(nextSessionId);
        }
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setError(err.message);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [apiBaseUrl, sessionId, siteKey]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, open, pending]);

  function animateAssistantMessage(messageId: string, answer: string, citations: Citation[], status: string) {
    let index = 0;
    const step = Math.max(1, Math.ceil(answer.length / 36));

    const tick = () => {
      index = Math.min(answer.length, index + step);
      setMessages((current) =>
        current.map((message) =>
          message.id === messageId
            ? {
                ...message,
                content: answer.slice(0, index),
                citations: index === answer.length ? citations : [],
                status,
              }
            : message,
        ),
      );

      if (index < answer.length) {
        window.setTimeout(tick, 18);
      }
    };

    tick();
  }

  async function submitWithRecovery(currentSessionId: string, message: string) {
    try {
      return await sendMessage(apiBaseUrl, siteKey, currentSessionId, message);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        const freshSessionId = await createSession(apiBaseUrl, siteKey);
        setSessionId(freshSessionId);
        return await sendMessage(apiBaseUrl, siteKey, freshSessionId, message);
      }
      throw error;
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || pending) {
      return;
    }

    setPending(true);
    setError(null);
    setOpen(true);
    setInput("");

    const userMessage: ChatMessage = {
      id: createId(),
      role: "user",
      content: trimmed,
      citations: [],
    };
    const assistantMessage: ChatMessage = {
      id: createId(),
      role: "assistant",
      content: "",
      citations: [],
      status: "pending",
    };

    setMessages((current) => [...current, userMessage, assistantMessage]);

    try {
      const ensuredSessionId = sessionId ?? (await createSession(apiBaseUrl, siteKey));
      if (!sessionId) {
        setSessionId(ensuredSessionId);
      }

      const result = await submitWithRecovery(ensuredSessionId, trimmed);
      animateAssistantMessage(assistantMessage.id, result.answer, result.citations, result.status);
    } catch (err) {
      const message = err instanceof Error ? err.message : "The assistant is unavailable right now.";
      setError(message);
      setMessages((current) =>
        current.map((entry) =>
          entry.id === assistantMessage.id
            ? {
                ...entry,
                content: "I cannot answer right now. Please try again in a moment.",
                citations: [],
                status: "error",
              }
            : entry,
        ),
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <div className={`rag-widget-shell ${inline ? "inline" : "floating"} ${open ? "is-open" : ""}`}>
      {!inline ? (
        <button className="rag-widget-launcher" onClick={() => setOpen((current) => !current)} type="button">
          {open ? "Close" : title}
        </button>
      ) : null}

      {(inline || open) && (
        <section className="rag-widget-panel">
          <header className="rag-widget-header">
            <div>
              <p className="rag-widget-kicker">Grounded answers only</p>
              <h2>{title}</h2>
            </div>
            {!inline ? (
              <button className="rag-widget-close" onClick={() => setOpen(false)} type="button">
                ×
              </button>
            ) : null}
          </header>

          <div className="rag-widget-messages">
            {messages.length === 0 ? (
              <div className="rag-widget-empty">
                Ask a question about the uploaded documents. If the evidence is weak, the bot will say it does not know.
              </div>
            ) : null}

            {messages.map((message) => (
              <article className={`rag-message rag-${message.role}`} key={message.id}>
                <p>{message.content || (message.status === "pending" ? "Thinking…" : "")}</p>
                {message.role === "assistant" && message.status === "insufficient_evidence" ? (
                  <span className="rag-message-tag">Insufficient evidence</span>
                ) : null}
                {message.citations.length > 0 ? (
                  <details className="rag-citations">
                    <summary>View citations</summary>
                    <div className="rag-citation-list">
                      {message.citations.map((citation, index) => (
                        <article className="rag-citation-card" key={`${message.id}-${index}`}>
                          <strong>{citation.filename}</strong>
                          <span>
                            {citation.page ? `Page ${citation.page}` : citation.section ?? "Document excerpt"}
                          </span>
                          <p>{citation.excerpt}</p>
                        </article>
                      ))}
                    </div>
                  </details>
                ) : null}
              </article>
            ))}
            <div ref={endRef} />
          </div>

          {error ? <p className="rag-widget-error">{error}</p> : null}

          <form className="rag-widget-form" onSubmit={handleSubmit}>
            <textarea
              onChange={(event) => setInput(event.target.value)}
              placeholder="Ask something that should be answered from the uploaded files..."
              rows={3}
              value={input}
            />
            <button disabled={pending || !input.trim()} type="submit">
              {pending ? "Working..." : "Send"}
            </button>
          </form>
        </section>
      )}
    </div>
  );
}
