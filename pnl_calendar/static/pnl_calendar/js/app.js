const THEME_KEY = "pnl-theme";
let pendingCalendarDirection = "next";

function applyTheme(theme) {
  const normalized = theme === "light" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", normalized);
  document.documentElement.style.colorScheme = normalized;
  localStorage.setItem(THEME_KEY, normalized);

  const toggle = document.querySelector("#theme-toggle");
  if (toggle) {
    toggle.checked = normalized === "light";
  }
}

function bindThemeToggle() {
  const toggle = document.querySelector("#theme-toggle");
  if (!toggle || toggle.dataset.bound === "true") {
    return;
  }

  const current = localStorage.getItem(THEME_KEY) === "light" ? "light" : "dark";
  toggle.checked = current === "light";

  toggle.addEventListener("change", () => {
    applyTheme(toggle.checked ? "light" : "dark");
  });

  toggle.dataset.bound = "true";
}

function primeMonthInput() {
  const monthInput = document.querySelector("#id_month");
  if (monthInput && !monthInput.value) {
    monthInput.valueAsDate = new Date();
  }
}

function replayEntranceAnimations(root) {
  const animated = root.querySelectorAll(".entrance-fade, .metric-cell");
  animated.forEach((node) => {
    node.classList.remove("entrance-fade");
    void node.offsetWidth;
    node.classList.add("entrance-fade");
  });
}

function stageSheets(root = document) {
  const nodes = root.querySelectorAll(".sheet, .metric-cell");
  nodes.forEach((node, index) => {
    node.classList.remove("staged-in");
    node.classList.add("staged");
    node.style.setProperty("--stagger-index", String(index));
  });

  requestAnimationFrame(() => {
    nodes.forEach((node) => node.classList.add("staged-in"));
  });
}

function bindCalendarDirection() {
  const links = document.querySelectorAll("[data-calendar-nav]");
  links.forEach((link) => {
    if (link.dataset.bound === "true") {
      return;
    }

    link.addEventListener("click", () => {
      pendingCalendarDirection = link.dataset.dir === "prev" ? "prev" : "next";
    });
    link.dataset.bound = "true";
  });
}

function bindScrollChrome() {
  const setScrolled = () => {
    document.body.classList.toggle("scrolled", window.scrollY > 8);
  };

  setScrolled();
  window.addEventListener("scroll", setScrolled, { passive: true });
}

function bindSettingsModal() {
  const modal = document.querySelector("#settings-modal");
  if (!modal || modal.dataset.bound === "true") {
    return;
  }

  modal.addEventListener("click", (event) => {
    if (event.target === modal) {
      modal.close();
    }
  });

  modal.dataset.bound = "true";
}

function bindCloseSettings() {
  const modal = document.querySelector("#settings-modal");
  const closeBtn = document.querySelector(".close-settings");
  if (!modal || !closeBtn || closeBtn.dataset.bound === "true") {
    return;
  }

  closeBtn.addEventListener("click", () => modal.close());
  closeBtn.dataset.bound = "true";
}

document.addEventListener("DOMContentLoaded", () => {
  const stored = localStorage.getItem(THEME_KEY);
  applyTheme(stored === "light" ? "light" : "dark");
  bindThemeToggle();
  bindCalendarDirection();
  bindScrollChrome();
  bindSettingsModal();
  primeMonthInput();
  stageSheets(document);
});

document.addEventListener("htmx:afterSwap", (event) => {
  if (event.target.id === "calendar-block") {
    primeMonthInput();
    replayEntranceAnimations(event.target);
    stageSheets(event.target);
    event.target.classList.remove("swap-in-next", "swap-in-prev");
    event.target.classList.add(
      pendingCalendarDirection === "prev" ? "swap-in-prev" : "swap-in-next"
    );
  }

  if (event.target.id === "settings-modal-content") {
    const modal = document.querySelector("#settings-modal");
    if (modal && !modal.open) {
      modal.showModal();
    }
    bindCloseSettings();
    bindThemeToggle();
    stageSheets(event.target);
  }

  bindCalendarDirection();
  bindThemeToggle();
});
