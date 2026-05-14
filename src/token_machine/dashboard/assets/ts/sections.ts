import { replayDonutAnimation } from "./charts.js";
import { datasetValue, optionalElement, queryAll } from "./dom.js";

export function initSectionToggles() {
  queryAll<HTMLElement>("[data-section-toggle]").forEach((toggle) => {
    const sectionId = datasetValue(toggle, "sectionToggle");
    if (!sectionId) return;
    const section = optionalElement(sectionId);
    if (!section) return;

    const applyState = (open: boolean, replay = false) => {
      const wasOpen = section.classList.contains("section-open");
      section.classList.toggle("section-open", open);
      section.classList.toggle("section-collapsed", !open);
      toggle.setAttribute("aria-expanded", String(open));
      if (open && (replay || !wasOpen)) {
        const donut = section.querySelector<HTMLElement>("#models-donut");
        if (donut) replayDonutAnimation(donut);
      }
    };

    applyState(toggle.getAttribute("aria-expanded") === "true");
    toggle.addEventListener("click", () => {
      applyState(!section.classList.contains("section-open"), true);
    });
  });
}
