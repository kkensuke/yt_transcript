(() => {
  "use strict";

  const colorScheme = document.querySelector('meta[name="color-scheme"]');
  if (colorScheme) colorScheme.setAttribute("content", "light dark");

  const ZOOM_LEVELS = [0.8, 0.9, 1, 1.1, 1.25, 1.5, 1.75, 2];
  let zoomIndex = ZOOM_LEVELS.indexOf(1);
  let zoomIndicatorTimer = null;

  function showZoomIndicator() {
    let indicator = document.getElementById("zoomIndicator");
    if (!indicator) {
      indicator = document.createElement("div");
      indicator.id = "zoomIndicator";
      indicator.className = "zoom-indicator";
      indicator.setAttribute("role", "status");
      indicator.setAttribute("aria-live", "polite");
      document.body.appendChild(indicator);
    }
    indicator.textContent = `${Math.round(ZOOM_LEVELS[zoomIndex] * 100)}%`;
    indicator.classList.add("visible");
    window.clearTimeout(zoomIndicatorTimer);
    zoomIndicatorTimer = window.setTimeout(() => indicator.classList.remove("visible"), 900);
  }

  function applyZoom(nextIndex) {
    zoomIndex = Math.max(0, Math.min(ZOOM_LEVELS.length - 1, nextIndex));
    document.documentElement.style.zoom = String(ZOOM_LEVELS[zoomIndex]);
    showZoomIndicator();
  }

  document.addEventListener("keydown", (event) => {
    if (!event.metaKey || event.ctrlKey || event.altKey) return;
    if (event.key === "=" || event.key === "+") {
      event.preventDefault();
      applyZoom(zoomIndex + 1);
    } else if (event.key === "-") {
      event.preventDefault();
      applyZoom(zoomIndex - 1);
    } else if (event.key === "0") {
      event.preventDefault();
      applyZoom(ZOOM_LEVELS.indexOf(1));
    }
  });

  const modelInput = document.getElementById("geminiModel");
  const modelSource = document.getElementById("geminiModelSource");
  const apiKeyInput = document.getElementById("apiKey");
  if (!modelInput || !modelSource || !apiKeyInput) return;

  const datalist = document.createElement("datalist");
  datalist.id = "geminiModelOptions";
  document.body.appendChild(datalist);
  modelInput.setAttribute("list", datalist.id);
  modelInput.setAttribute("autocomplete", "off");

  const tools = document.createElement("div");
  tools.className = "model-tools";
  const loadButton = document.createElement("button");
  loadButton.type = "button";
  loadButton.className = "button button-secondary model-load-button";
  loadButton.textContent = "Load available models";
  const status = document.createElement("span");
  status.className = "model-list-status";
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  tools.append(loadButton, status);
  modelSource.insertAdjacentElement("afterend", tools);

  async function loadModels({ quiet = false } = {}) {
    if (!window.pywebview || !window.pywebview.api) return;
    loadButton.disabled = true;
    if (!quiet) status.textContent = "Loading…";
    try {
      const response = await window.pywebview.api.list_gemini_models(apiKeyInput.value.trim());
      if (!response || !response.ok) {
        if (!quiet) status.textContent = (response && response.error) || "Could not load models.";
        return;
      }
      const models = Array.isArray(response.models) ? response.models : [];
      datalist.replaceChildren(
        ...models.map((model) => {
          const option = document.createElement("option");
          option.value = model;
          return option;
        }),
      );
      status.textContent = models.length ? `${models.length} models available` : "No models found";
    } catch (error) {
      if (!quiet) status.textContent = `Could not load models: ${String(error)}`;
    } finally {
      loadButton.disabled = false;
    }
  }

  loadButton.addEventListener("click", () => loadModels());
  window.addEventListener(
    "pywebviewready",
    async () => {
      try {
        const info = await window.pywebview.api.get_app_info();
        if (info && info.api_key_configured) await loadModels({ quiet: true });
      } catch (_error) {
        // The main UI owns bridge error reporting.
      }
    },
    { once: true },
  );
})();
