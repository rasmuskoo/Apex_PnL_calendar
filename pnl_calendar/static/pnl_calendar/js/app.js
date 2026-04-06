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

function formatDate(value) {
  const y = value.getFullYear();
  const m = String(value.getMonth() + 1).padStart(2, "0");
  const d = String(value.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function addDays(value, days) {
  const next = new Date(value);
  next.setDate(next.getDate() + days);
  return next;
}

function addMonths(value, months) {
  const next = new Date(value);
  const day = next.getDate();
  next.setDate(1);
  next.setMonth(next.getMonth() + months);
  const maxDay = new Date(next.getFullYear(), next.getMonth() + 1, 0).getDate();
  next.setDate(Math.min(day, maxDay));
  return next;
}

function addYears(value, years) {
  const next = new Date(value);
  const month = next.getMonth();
  const day = next.getDate();
  next.setFullYear(next.getFullYear() + years, month, day);
  if (next.getMonth() !== month) {
    next.setDate(0);
  }
  return next;
}

function hotRangeBounds(rangeKey) {
  const today = new Date();
  let start = null;
  let end = null;

  if (rangeKey === "today") {
    start = today;
    end = today;
  } else if (rangeKey === "yesterday") {
    start = addDays(today, -1);
    end = addDays(today, -1);
  } else if (rangeKey === "this_week") {
    start = addDays(today, -6);
    end = today;
  } else if (rangeKey === "previous_week") {
    end = addDays(today, -7);
    start = addDays(end, -6);
  } else if (rangeKey === "this_month") {
    start = addDays(addMonths(today, -1), 1);
    end = today;
  } else if (rangeKey === "previous_month") {
    const thisStart = addDays(addMonths(today, -1), 1);
    end = addDays(thisStart, -1);
    start = addDays(addMonths(end, -1), 1);
  } else if (rangeKey === "this_quarter") {
    start = addDays(addMonths(today, -3), 1);
    end = today;
  } else if (rangeKey === "previous_quarter") {
    const thisStart = addDays(addMonths(today, -3), 1);
    end = addDays(thisStart, -1);
    start = addDays(addMonths(end, -3), 1);
  } else if (rangeKey === "this_year") {
    start = addDays(addYears(today, -1), 1);
    end = today;
  } else if (rangeKey === "previous_year") {
    const thisStart = addDays(addYears(today, -1), 1);
    end = addDays(thisStart, -1);
    start = addDays(addYears(end, -1), 1);
  }

  if (!start || !end) {
    return null;
  }
  return { start: formatDate(start), end: formatDate(end) };
}

function bindHotRangeFilters() {
  const rangeSelect = document.querySelector("#id_hot_range");
  const dateFrom = document.querySelector("#id_date_from");
  const dateTo = document.querySelector("#id_date_to");
  if (!rangeSelect || !dateFrom || !dateTo || rangeSelect.dataset.bound === "true") {
    return;
  }

  rangeSelect.addEventListener("change", () => {
    const selected = rangeSelect.value;
    if (!selected || selected === "custom") {
      return;
    }
    const bounds = hotRangeBounds(selected);
    if (!bounds) {
      return;
    }
    dateFrom.value = bounds.start;
    dateTo.value = bounds.end;
  });

  const forceCustom = () => {
    rangeSelect.value = "custom";
  };
  dateFrom.addEventListener("change", forceCustom);
  dateTo.addEventListener("change", forceCustom);

  rangeSelect.dataset.bound = "true";
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
  bindHotRangeFilters();
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
  bindHotRangeFilters();
  bindThemeToggle();
});
