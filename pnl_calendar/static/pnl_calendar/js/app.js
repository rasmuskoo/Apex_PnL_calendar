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

function stageSheets(root = document) {
  // Performance mode: disable staged entrance work.
  void root;
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
  // Disabled for responsiveness.
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

function bindDayPopup() {
  const popup = document.querySelector("#day-popup");
  const dateLabel = document.querySelector("#day-popup-date");
  const addTradeBtn = document.querySelector("#day-popup-add-trade");
  const tradeForm = document.querySelector("#day-trade-form");
  const tradeDateInput = document.querySelector("#id_trade_date");
  const statusTargets = document.querySelectorAll(".popup-day-target");
  if (!popup || !dateLabel || !addTradeBtn || !tradeForm || !tradeDateInput) {
    return;
  }

  if (popup.dataset.bound !== "true") {
    popup.addEventListener("click", (event) => {
      if (event.target === popup) {
        popup.close();
      }
    });
    addTradeBtn.addEventListener("click", () => {
      tradeForm.classList.toggle("show");
    });

    const openPopup = () => {
      if (typeof popup.showModal === "function") {
        if (!popup.open) {
          popup.showModal();
        }
      } else {
        popup.setAttribute("open", "open");
      }
    };

    document.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) {
        return;
      }
      const cell = event.target.closest("[data-day-cell]");
      if (!cell) {
        return;
      }
      const day = cell.dataset.day;
      if (!day) {
        return;
      }
      dateLabel.textContent = day;
      tradeDateInput.value = day;
      statusTargets.forEach((input) => {
        input.value = day;
      });
      tradeForm.classList.remove("show");
      openPopup();
    });
    popup.dataset.bound = "true";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const stored = localStorage.getItem(THEME_KEY);
  applyTheme(stored === "light" ? "light" : "dark");
  bindThemeToggle();
  bindCalendarDirection();
  bindScrollChrome();
  bindHotRangeFilters();
  bindSettingsModal();
  bindDayPopup();
  primeMonthInput();
});

document.addEventListener("htmx:afterSwap", (event) => {
  if (event.target.id === "calendar-block") {
    primeMonthInput();
  }

  if (event.target.id === "settings-modal-content") {
    const modal = document.querySelector("#settings-modal");
    if (modal && !modal.open) {
      modal.showModal();
    }
    bindCloseSettings();
    bindThemeToggle();
  }

  bindCalendarDirection();
  bindHotRangeFilters();
  bindThemeToggle();
  bindDayPopup();
});
