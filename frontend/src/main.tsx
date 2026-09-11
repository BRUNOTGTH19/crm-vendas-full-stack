import { createRoot } from "react-dom/client";
import { App } from "./App.tsx";
import "./index.css";

// Registrar la PWA (solo en http/https, no en file://)
if ("serviceWorker" in navigator && location.protocol.startsWith("http")) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}

const root = document.getElementById("root");
if (root) {
  createRoot(root).render(<App />);
}