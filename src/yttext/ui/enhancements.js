(() => {
  "use strict";

  const colorScheme = document.querySelector('meta[name="color-scheme"]');
  if (colorScheme) colorScheme.setAttribute("content", "light dark");

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

  async function loadModels() {
    const apiKey = apiKeyInput.value.trim();
    const serverApiKey = Boolean(window.App?.hasServerApiKey?.());
    if (!apiKey && !serverApiKey) {
      status.textContent = "Enter your Gemini API key first.";
      apiKeyInput.focus();
      return;
    }
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
      datalist.replaceChildren(
        ...models.map((model) => {
          const option = document.createElement("option");
          option.value = model;
          return option;
        }),
      );
      status.textContent = models.length ? `${models.length} models available` : "No models found";
    } catch (_error) {
      status.textContent = "Could not load models. Check your connection and try again.";
    } finally {
      loadButton.disabled = false;
    }
  }

  loadButton.addEventListener("click", () => loadModels());
})();
