import widget from "./embed";

const previewTarget = document.getElementById("widget-preview");
if (!previewTarget) {
  throw new Error("Nie znaleziono elementu podglądu widżetu.");
}

document.body.style.margin = "0";
document.body.style.minHeight = "100vh";
document.body.style.background = "linear-gradient(180deg, #f1efe7 0%, #dbded7 100%)";
document.body.style.display = "grid";
document.body.style.placeItems = "center";
document.body.style.padding = "1rem";

widget.init({
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000",
  inline: true,
  siteKey: import.meta.env.VITE_SITE_KEY ?? "local-demo-key",
  target: previewTarget,
  title: "Podgląd widżetu RAG",
});
