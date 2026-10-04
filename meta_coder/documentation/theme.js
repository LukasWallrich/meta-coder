(() => {
  const key = "meta-coder-theme";
  const media = matchMedia("(prefers-color-scheme: dark)");
  let preference = "system";
  function apply(value) {
    preference = ["system", "light", "dark"].includes(value) ? value : "system";
    const dark = preference === "dark" || (preference === "system" && media.matches);
    document.documentElement.classList.toggle("dark", dark);
    document.documentElement.style.colorScheme = dark ? "dark" : "light";
    const select = document.getElementById("docs-theme");
    if (select) select.value = preference;
  }
  try { preference = localStorage.getItem(key) || "system"; } catch (_) {}
  apply(preference);
  media.addEventListener("change", () => apply(preference));
  window.addEventListener("storage", event => { if (event.key === key) apply(event.newValue); });
  document.addEventListener("DOMContentLoaded", () => {
    apply(preference);
    document.getElementById("docs-theme").addEventListener("change", event => {
      apply(event.target.value);
      try { localStorage.setItem(key, preference); } catch (_) {}
    });
    // Only bundled documentation has a token prefix; standalone MkDocs has no app link.
    const match = location.pathname.match(/^\/([^/]+)\/docs(?:\/|$)/);
    if (match && ["127.0.0.1", "localhost"].includes(location.hostname)) {
      const link = document.getElementById("back-to-app");
      link.href = "/" + match[1] + "/";
      link.hidden = false;
    }
    if (matchMedia("(max-width: 760px)").matches) document.getElementById("docs-navigation").open = false;
  });
})();
