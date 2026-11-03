// Opens Impressum and Datenschutz in a glass window instead of navigating away.
// The pages stay as normal links, so without JavaScript (or on failure) the link simply opens the page.
(() => {
  const PAGES = /(^|\/)(impressum|datenschutz)\.html$/;
  const cache = new Map();
  let dialog;

  function build() {
    dialog = document.createElement("dialog");
    dialog.className = "legal-modal";
    dialog.setAttribute("aria-labelledby", "legal-modal-title");
    dialog.innerHTML = '<header><h2 id="legal-modal-title"></h2><button type="button" class="legal-close" aria-label="Schließen">×</button></header><div class="legal-body"></div>';
    dialog.querySelector(".legal-close").addEventListener("click", () => dialog.close());
    // A click on the dimmed area outside the window closes it.
    dialog.addEventListener("click", event => { if (event.target === dialog) dialog.close(); });
    dialog.addEventListener("close", () => {
      document.body.classList.remove("legal-open");
      if (/^#(impressum|datenschutz)$/.test(location.hash)) history.replaceState(null, "", location.pathname + location.search);
    });
    document.body.appendChild(dialog);
  }

  async function content(url) {
    if (!cache.has(url)) {
      cache.set(url, fetch(url).then(response => {
        if (!response.ok) throw new Error(response.status);
        return response.text();
      }).then(html => {
        const main = new DOMParser().parseFromString(html, "text/html").querySelector("main");
        main.querySelector(".back")?.remove();
        const title = main.querySelector("h1");
        const heading = title ? title.textContent : "";
        title?.remove();
        return { heading, body: main.innerHTML };
      }).catch(error => { cache.delete(url); throw error; }));
    }
    return cache.get(url);
  }

  async function open(url) {
    if (!dialog) build();
    const page = await content(url);
    dialog.querySelector("h2").textContent = page.heading;
    const body = dialog.querySelector(".legal-body");
    body.innerHTML = page.body;
    body.scrollTop = 0;
    if (!dialog.open) dialog.showModal();
    document.body.classList.add("legal-open");
    dialog.querySelector(".legal-close").focus();
  }

  document.addEventListener("click", event => {
    const link = event.target.closest("a[href]");
    if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const url = new URL(link.getAttribute("href"), location.href);
    if (url.origin !== location.origin || !PAGES.test(url.pathname) || typeof HTMLDialogElement !== "function") return;
    event.preventDefault();
    open(url.href).then(() => history.replaceState(null, "", "#" + url.pathname.match(PAGES)[2])).catch(() => { location.href = url.href; });
  });

  // Direct links such as …/#impressum open the window right away.
  const start = location.hash.match(/^#(impressum|datenschutz)$/);
  if (start && typeof HTMLDialogElement === "function") open(new URL(start[1] + ".html", location.href).href).catch(() => {});
})();
