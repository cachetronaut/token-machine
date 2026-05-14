import { replayDonutAnimation } from "./charts.js";

export function initSectionToggles() {
  document.querySelectorAll("[data-section-toggle]").forEach((toggle) => {
    const sectionId = toggle.getAttribute("data-section-toggle");
    if (!sectionId) return;
    const section = document.getElementById(sectionId);
    if (!section) return;

    const applyState = (open, replay = false) => {
      const wasOpen = section.classList.contains("section-open");
      section.classList.toggle("section-open", open);
      section.classList.toggle("section-collapsed", !open);
      toggle.setAttribute("aria-expanded", String(open));
      if (open && (replay || !wasOpen)) {
        const donut = section.querySelector("#models-donut");
        if (donut) replayDonutAnimation(donut);
      }
    };

    applyState(toggle.getAttribute("aria-expanded") === "true");
    toggle.addEventListener("click", () => {
      applyState(!section.classList.contains("section-open"), true);
    });
  });
}
