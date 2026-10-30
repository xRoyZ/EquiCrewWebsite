/* EquiCrew site script (no dependencies), loaded with `defer` on every page.
   It only enhances what the HTML already holds:
   - the phone menu: button.nav-toggle opens and closes #site-nav (aria-expanded), Escape
     closes it and returns focus to the button, a click on a link or outside closes it;
   - the current year in every [data-year];
   - the scroll reveal of [data-reveal] blocks below the first screen (a fade; content is
     visible without scripts, and nothing is hidden or animated under
     prefers-reduced-motion: reduce). */
(() => {
  "use strict";

  const doc = document;
  const WIDE_QUERY = "(min-width: 801px)";
  const REDUCED_QUERY = "(prefers-reduced-motion: reduce)";

  const media = (query) =>
    typeof window.matchMedia === "function" ? window.matchMedia(query) : null;

  const onMediaChange = (list, handler) => {
    if (!list) return;
    if (typeof list.addEventListener === "function") list.addEventListener("change", handler);
    else if (typeof list.addListener === "function") list.addListener(handler);
  };

  const initMenu = () => {
    const toggle = doc.querySelector("button.nav-toggle");
    if (!toggle) return;
    const nav = doc.getElementById(toggle.getAttribute("aria-controls") || "site-nav");
    if (!nav) return;

    const isOpen = () => toggle.getAttribute("aria-expanded") === "true";

    const setOpen = (open) => {
      nav.classList.toggle("is-open", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    };

    setOpen(false);

    toggle.addEventListener("click", () => {
      setOpen(!isOpen());
    });

    doc.addEventListener("keydown", (event) => {
      if ((event.key === "Escape" || event.key === "Esc") && isOpen()) {
        setOpen(false);
        toggle.focus();
      }
    });

    nav.addEventListener("click", (event) => {
      const target = event.target;
      if (target && typeof target.closest === "function" && target.closest("a")) setOpen(false);
    });

    doc.addEventListener("click", (event) => {
      if (!isOpen()) return;
      if (nav.contains(event.target) || toggle.contains(event.target)) return;
      setOpen(false);
    });

    // Back on a wide screen the links sit inline; drop a menu left open on the phone layout.
    onMediaChange(media(WIDE_QUERY), (event) => {
      if (event.matches) setOpen(false);
    });
  };

  const initYear = () => {
    const year = String(new Date().getFullYear());
    for (const node of doc.querySelectorAll("[data-year]")) node.textContent = year;
  };

  const initReveal = () => {
    const nodes = Array.from(doc.querySelectorAll("[data-reveal]"));
    if (!nodes.length) return;
    if (typeof window.IntersectionObserver !== "function") return;
    const reduced = media(REDUCED_QUERY);
    if (reduced && reduced.matches) return;

    const observer = new window.IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          entry.target.classList.remove("is-reveal-pending");
          entry.target.classList.add("is-revealed");
          observer.unobserve(entry.target);
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0 },
    );

    // Only blocks that start below the first screen are hidden until they scroll in.
    const fold = window.innerHeight || doc.documentElement.clientHeight || 0;
    for (const node of nodes) {
      if (node.getBoundingClientRect().top < fold) continue;
      node.classList.add("is-reveal-pending");
      observer.observe(node);
    }

    // If the visitor switches to reduced motion meanwhile, show everything at once.
    onMediaChange(reduced, (event) => {
      if (!event.matches) return;
      observer.disconnect();
      for (const node of nodes) node.classList.remove("is-reveal-pending");
    });
  };

  initMenu();
  initYear();
  initReveal();
})();
