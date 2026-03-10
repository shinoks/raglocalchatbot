import { createRoot, Root } from "react-dom/client";

import { WidgetApp } from "./components/WidgetApp";
import { widgetStyles } from "./widgetStyles";

type InitOptions = {
  apiBaseUrl: string;
  inline?: boolean;
  siteKey: string;
  target?: HTMLElement;
  title?: string;
};

type WidgetHandle = {
  destroy: () => void;
};

const mountedRoots = new WeakMap<HTMLElement, Root>();
const STYLE_TAG_ID = "rag-widget-inline-styles";

function ensureStyles() {
  if (document.getElementById(STYLE_TAG_ID)) {
    return;
  }

  const style = document.createElement("style");
  style.id = STYLE_TAG_ID;
  style.textContent = widgetStyles;
  document.head.appendChild(style);
}

function init(options: InitOptions): WidgetHandle {
  ensureStyles();

  const host = options.target ?? document.createElement("div");
  if (!options.target) {
    document.body.appendChild(host);
  }

  const existingRoot = mountedRoots.get(host);
  existingRoot?.unmount();

  const root = createRoot(host);
  mountedRoots.set(host, root);
  root.render(
    <WidgetApp
      apiBaseUrl={options.apiBaseUrl}
      inline={options.inline}
      siteKey={options.siteKey}
      title={options.title}
    />,
  );

  return {
    destroy() {
      root.unmount();
      mountedRoots.delete(host);
      if (!options.target && host.parentNode) {
        host.parentNode.removeChild(host);
      }
    },
  };
}

const api = { init };

declare global {
  interface Window {
    RagWidget: typeof api;
  }
}

if (typeof window !== "undefined") {
  window.RagWidget = api;
}

export default api;
