(() => {
  "use strict";

  const systemPrefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  let currentTheme = systemPrefersDark ? "dark" : "light";

  function applyTheme(theme) {
    currentTheme = theme === "dark" ? "dark" : "light";
    document.documentElement.dataset.theme = currentTheme;
    document.documentElement.style.colorScheme = currentTheme;

    const controls = document.querySelectorAll("[data-theme-choice]");
    controls.forEach((button) => {
      const selected = button.dataset.themeChoice === currentTheme;
      button.classList.toggle("active", selected);
      button.setAttribute("aria-pressed", selected ? "true" : "false");
    });
  }

  function installThemeControl() {
    const header = document.querySelector(".app-header");
    const bridgeStatus = document.getElementById("bridgeStatus");
    if (!header || !bridgeStatus || document.getElementById("themeControl")) return;

    const actions = document.createElement("div");
    actions.className = "header-actions";

    const control = document.createElement("div");
    control.id = "themeControl";
    control.className = "theme-control";
    control.setAttribute("role", "group");
    control.setAttribute("aria-label", "Appearance");

    for (const [theme, label] of [["light", "Light"], ["dark", "Dark"]]) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "theme-choice";
      button.dataset.themeChoice = theme;
      button.textContent = label;
      button.setAttribute("aria-pressed", "false");
      button.addEventListener("click", () => applyTheme(theme));
      control.appendChild(button);
    }

    header.insertBefore(actions, bridgeStatus);
    actions.append(control, bridgeStatus);
    applyTheme(currentTheme);
  }

  // Resolve the launch appearance once. Later macOS appearance changes do not
  // override an in-app Light/Dark choice during this app session.
  applyTheme(currentTheme);

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", installThemeControl, { once: true });
  } else {
    installThemeControl();
  }
})();
