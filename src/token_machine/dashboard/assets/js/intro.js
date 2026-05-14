const SESSION_KEY = "tm-intro-played";

function seedWarp(warp) {
  if (!warp) return;
  const COUNT = 90;
  const TOTAL_WINDOW = 1700;
  const frag = document.createDocumentFragment();
  for (let n = 0; n < COUNT; n++) {
    const i = document.createElement("i");
    const angle = Math.random() * 360;
    const start = 18 + Math.random() * 140;
    const end   = 640 + Math.random() * 360;
    const dur   = 520 + Math.random() * 620;
    const delay = Math.random() * TOTAL_WINDOW;
    const thick = (0.9 + Math.random() * 1.4).toFixed(2);
    const tint  = Math.random() < 0.18 ? "#ffffff" : "var(--teal)";
    i.style.setProperty("--angle", angle + "deg");
    i.style.setProperty("--start", start + "px");
    i.style.setProperty("--end",   end + "px");
    i.style.setProperty("--dur",   dur + "ms");
    i.style.setProperty("--delay", delay + "ms");
    i.style.setProperty("--thick", thick + "px");
    i.style.setProperty("--tint",  tint);
    frag.appendChild(i);
  }
  warp.appendChild(frag);
}

function typeOn(el, text, perChar, startDelay, timers) {
  timers.push(setTimeout(() => {
    el.textContent = "";
    for (let k = 0; k < text.length; k++) {
      timers.push(setTimeout(() => {
        el.textContent = text.slice(0, k + 1);
      }, k * perChar));
    }
  }, startDelay));
}

function backspaceThenType(el, fromText, toText, timers, startDelay) {
  timers.push(setTimeout(() => {
    for (let k = 0; k < fromText.length; k++) {
      timers.push(setTimeout(() => {
        el.textContent = fromText.slice(0, fromText.length - 1 - k);
      }, k * 35));
    }
    const afterBackspace = fromText.length * 35 + 120;
    typeOn(el, toText, 70, afterBackspace, timers);
  }, startDelay));
}

export function playIntro({ force = false } = {}) {
  if (!force && sessionStorage.getItem(SESSION_KEY) === "1") return;
  if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    sessionStorage.setItem(SESSION_KEY, "1");
    return;
  }

  const overlay = document.createElement("div");
  overlay.className = "intro-overlay";
  overlay.setAttribute("aria-hidden", "true");
  overlay.innerHTML = `
    <div class="intro-stage">
      <div class="intro-warp"></div>
      <div class="intro-brackets"><span></span><span></span><span></span><span></span></div>
      <div class="intro-wordmark">
        <svg viewBox="0 0 600 80" aria-label="Token Machine">
          <text class="intro-stroke" x="50%" y="62" text-anchor="middle">TOKEN MACHINE</text>
          <text class="intro-fill"   x="50%" y="62" text-anchor="middle">TOKEN MACHINE</text>
        </svg>
        <div class="intro-caption"><span class="intro-cap-text"></span><span class="intro-cursor">▌</span></div>
      </div>
      <div class="intro-pulse-ring"></div>
    </div>
  `;
  document.body.appendChild(overlay);
  document.body.style.overflow = "hidden";

  const warp = overlay.querySelector(".intro-warp");
  const cap = overlay.querySelector(".intro-cap-text");
  const timers = [];

  seedWarp(warp);
  typeOn(cap, "INITIALIZING", 55, 2100, timers);
  backspaceThenType(cap, "INITIALIZING", "ONLINE", timers, 3300);

  const DISMISS_AT = 4500;
  timers.push(setTimeout(() => {
    overlay.classList.add("intro-done");
    setTimeout(() => {
      overlay.remove();
      document.body.style.overflow = "";
      sessionStorage.setItem(SESSION_KEY, "1");
    }, 600);
  }, DISMISS_AT));
}
