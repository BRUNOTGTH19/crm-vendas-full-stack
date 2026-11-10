// Anti-flash: aplica o tema salvo antes do React montar (chave `crm:theme`).
// Fica em arquivo próprio para que a CSP use `script-src 'self'` sem
// `'unsafe-inline'` (A12 da auditoria).
(function () {
  try {
    var stored = localStorage.getItem("crm:theme");
    var pref =
      stored === "dark" || stored === "light" || stored === "system" ? stored : "light";
    var dark =
      pref === "dark" ||
      (pref === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
    var root = document.documentElement;
    root.classList.toggle("dark", dark);
    root.style.colorScheme = dark ? "dark" : "light";
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", dark ? "#08100C" : "#F5F2EA");
  } catch (error) {
    /* storage indisponível: segue o padrão claro */
  }
})();
