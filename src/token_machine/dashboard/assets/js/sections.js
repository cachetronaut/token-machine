export function initSectionToggles() {
  document.querySelectorAll("[data-section-toggle]").forEach((toggle) => {
    const sectionId = toggle.getAttribute("data-section-toggle");
    const section = document.getElementById(sectionId);
    if (!section) return;

    const applyState = (open) => {
      section.classList.toggle("section-open", open);
      section.classList.toggle("section-collapsed", !open);
      toggle.setAttribute("aria-expanded", String(open));
    };

    applyState(toggle.getAttribute("aria-expanded") === "true");
    toggle.addEventListener("click", () => {
      applyState(!section.classList.contains("section-open"));
    });
  });
}
