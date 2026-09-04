(() => {
  "use strict";

  const colorScheme = document.querySelector('meta[name="color-scheme"]');
  if (colorScheme) colorScheme.setAttribute("content", "light dark");

  const modelSelect = document.getElementById("geminiModel");
  const modelSource = document.getElementById("geminiModelSource");
  const apiKeyInput = document.getElementById("apiKey");
  if (!modelSelect || !modelSource || !apiKeyInput) return;

  let serverApiKey = false;

  const tools = document.createElement("div");
  tools.className = "model-tools";
  const loadButton = document.createElement("button");
  loadButton.type = "button";
  loadButton.className = "button button-secondary model-load-button";
  loadButton.textContent = "Load available models";
  loadButton.disabled = true;
  const status = document.createElement("span");
  status.className = "model-list-status";
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  tools.append(loadButton, status);
  modelSource.insertAdjacentElement("afterend", tools);

  function showConfiguredModel(model) {
    const value = String(model || "").trim();
    if (!value) return;
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    modelSelect.replaceChildren(option);
    modelSelect.value = value;
  }

  async function loadModels() {
    const apiKey = apiKeyInput.value.trim();
    if (!apiKey && !serverApiKey) {
      status.textContent = "Enter your Gemini API key first.";
      apiKeyInput.focus();
      return;
    }

    const preferredModel = modelSelect.value;
    loadButton.disabled = true;
    status.textContent = "Loading…";
    try {
      const headers = {
        Accept: "application/json",
        "Content-Type": "application/json",
      };
      if (apiKey) headers["X-Gemini-Api-Key"] = apiKey;
      const response = await fetch("/api/gemini/models", {
        method: "POST",
        headers,
        body: "{}",
        cache: "no-store",
        credentials: "omit",
      });
      let payload = null;
      try {
        payload = await response.json();
      } catch (_error) {
        // Use the generic message below for a non-JSON server response.
      }
      if (!response.ok) {
        status.textContent = payload?.error?.message || "Could not load models.";
        return;
      }

      const models = Array.isArray(payload?.models) ? payload.models : [];
      if (!models.length) {
        status.textContent = "No models found";
        return;
      }

      const options = models.map((model) => {
        const option = document.createElement("option");
        option.value = model;
        option.textContent = model;
        return option;
      });
      if (preferredModel && models.includes(preferredModel)) {
        modelSelect.replaceChildren(...options);
        modelSelect.value = preferredModel;
        status.textContent = `${models.length} models available`;
      } else {
        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = "Choose a Gemini model";
        placeholder.disabled = true;
        placeholder.selected = true;
        modelSelect.replaceChildren(placeholder, ...options);
        status.textContent = preferredModel
          ? `${models.length} models available; current setting is unavailable`
          : `${models.length} models available`;
      }
      loadButton.textContent = "Refresh models";
    } catch (_error) {
      status.textContent = "Could not load models. Check your connection and try again.";
    } finally {
      loadButton.disabled = false;
    }
  }

  async function initializeModels() {
    try {
      const response = await fetch("/api/info", {
        headers: { Accept: "application/json" },
        cache: "no-store",
        credentials: "omit",
      });
      if (!response.ok) return;
      const appInfo = await response.json();
      showConfiguredModel(appInfo?.gemini_model);
      serverApiKey = Boolean(appInfo?.capabilities?.server_api_key);
      loadButton.disabled = false;
      if (serverApiKey) await loadModels();
    } catch (_error) {
      loadButton.disabled = false;
    }
  }

  loadButton.addEventListener("click", () => loadModels());
  initializeModels();
})();
