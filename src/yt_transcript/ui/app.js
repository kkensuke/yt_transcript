(() => {
  "use strict";

  const elements = {
    form: document.getElementById("extractForm"),
    executeFormTab: document.getElementById("executeFormTab"),
    settingsFormTab: document.getElementById("settingsFormTab"),
    executeFormPanel: document.getElementById("executeFormPanel"),
    settingsFormPanel: document.getElementById("settingsFormPanel"),
    videoUrl: document.getElementById("videoUrl"),
    urlError: document.getElementById("urlError"),
    transcriptFormat: document.getElementById("transcriptFormat"),
    summary: document.getElementById("summaryToggle"),
    summaryOptions: document.getElementById("summaryOptions"),
    summaryLanguage: document.getElementById("summaryLanguage"),
    cookieBrowser: document.getElementById("cookieBrowser"),
    apiKey: document.getElementById("apiKey"),
    apiKeyLabel: document.getElementById("apiKeyLabel"),
    apiKeyNote: document.getElementById("apiKeyNote"),
    apiKeyError: document.getElementById("apiKeyError"),
    apiKeySource: document.getElementById("apiKeySource"),
    apiKeySourceTitle: document.getElementById("apiKeySourceTitle"),
    apiKeySourceDescription: document.getElementById("apiKeySourceDescription"),
    apiKeyVisibilityButton: document.getElementById("apiKeyVisibilityButton"),
    geminiModel: document.getElementById("geminiModel"),
    geminiModelSource: document.getElementById("geminiModelSource"),
    extractButton: document.getElementById("extractButton"),
    extractButtonLabel: document.querySelector("#extractButton .button-label"),
    runSummary: document.getElementById("runSummary"),
    submitHelp: document.getElementById("submitHelp"),
    bridgeStatus: document.getElementById("bridgeStatus"),
    versionLabel: document.getElementById("versionLabel"),
    progressPanel: document.getElementById("progressPanel"),
    progressMessage: document.getElementById("progressMessage"),
    progressPercent: document.getElementById("progressPercent"),
    progressBar: document.getElementById("progressBar"),
    errorPanel: document.getElementById("errorPanel"),
    errorMessage: document.getElementById("errorMessage"),
    errorHint: document.getElementById("errorHint"),
    resultPanel: document.getElementById("resultPanel"),
    resultTitle: document.getElementById("resultTitle"),
    resultMeta: document.getElementById("resultMeta"),
    warningBanner: document.getElementById("warningBanner"),
    summaryLimitPanel: document.getElementById("summaryLimitPanel"),
    summaryLimitMessage: document.getElementById("summaryLimitMessage"),
    transcriptTab: document.getElementById("transcriptTab"),
    transcriptFormatBadge: document.getElementById("transcriptFormatBadge"),
    summaryActionGroup: document.getElementById("summaryActionGroup"),
    summaryTab: document.getElementById("summaryTab"),
    markdownOutput: document.getElementById("markdownOutput"),
    copyTranscriptButton: document.getElementById("copyTranscriptButton"),
    saveTranscriptButton: document.getElementById("saveTranscriptButton"),
    copySummaryButton: document.getElementById("copySummaryButton"),
    saveSummaryButton: document.getElementById("saveSummaryButton"),
    combinedResultActions: document.getElementById("combinedResultActions"),
    saveBothButton: document.getElementById("saveBothButton"),
    openVideoButton: document.getElementById("openVideoButton"),
    toastRegion: document.getElementById("toastRegion"),
  };

  const state = {
    bridgeReady: false,
    busy: false,
    appInfo: {
      api_key_configured: false,
      api_key_source: "not_configured",
      api_key_environment_variable: "GEMINI_API_KEY",
      gemini_model: "gemini-flash-lite-latest",
      gemini_model_source: "default",
      gemini_model_environment_variable: "GEMINI_MODEL",
    },
    result: null,
    activeFormTab: "execute",
    activeTab: "transcript",
  };

  window.App = {
    onProgress(payload) {
      const percent = Math.max(0, Math.min(100, Number(payload.percent) || 0));
      elements.progressMessage.textContent = payload.message || "Processing…";
      elements.progressPercent.textContent = `${percent}%`;
      elements.progressBar.style.width = `${percent}%`;
    },
  };

  window.addEventListener("pywebviewready", initializeBridge, { once: true });
  elements.form.addEventListener("submit", handleSubmit);
  elements.summary.addEventListener("change", syncSummaryOptions);
  elements.transcriptFormat.addEventListener("change", updateExecutionSummary);
  elements.summaryLanguage.addEventListener("change", updateExecutionSummary);
  elements.cookieBrowser.addEventListener("change", updateExecutionSummary);
  elements.videoUrl.addEventListener("input", () => {
    clearUrlError();
    syncActionState();
  });
  elements.apiKey.addEventListener("input", clearApiKeyError);
  elements.apiKeyVisibilityButton.addEventListener("click", toggleApiKeyVisibility);
  elements.copyTranscriptButton.addEventListener("click", () => copyResult("transcript"));
  elements.saveTranscriptButton.addEventListener("click", () =>
    saveResult("transcript", elements.saveTranscriptButton));
  elements.copySummaryButton.addEventListener("click", () => copyResult("summary"));
  elements.saveSummaryButton.addEventListener("click", () =>
    saveResult("summary", elements.saveSummaryButton));
  elements.saveBothButton.addEventListener("click", saveBothResults);
  elements.openVideoButton.addEventListener("click", openCurrentVideo);
  elements.markdownOutput.addEventListener("click", handleOutputLink);
  document.querySelectorAll("[data-summary-mode]").forEach((button) => {
    button.addEventListener("click", () => resolveLongSummary(button.dataset.summaryMode));
  });
  document.querySelectorAll("[data-form-tab]").forEach((button) => {
    button.addEventListener("click", () => switchFormTab(button.dataset.formTab));
  });
  document.querySelectorAll("[data-tab]").forEach((button) => {
    button.addEventListener("click", () => switchTab(button.dataset.tab));
  });
  switchFormTab("execute");
  syncSummaryOptions();
  updateExecutionSummary();
  syncActionState();

  async function initializeBridge() {
    try {
      state.appInfo = await window.pywebview.api.get_app_info();
      state.bridgeReady = true;
      elements.geminiModel.value = state.appInfo.gemini_model || "gemini-flash-lite-latest";
      elements.versionLabel.textContent = `v${state.appInfo.version || ""}`;
      elements.bridgeStatus.className = "status-pill status-ready";
      elements.bridgeStatus.innerHTML = '<span class="status-dot"></span><span>Ready</span>';
      renderConfigurationSources();
      updateExecutionSummary();
      syncActionState();
      elements.videoUrl.focus();
    } catch (error) {
      elements.bridgeStatus.className = "status-pill status-error";
      elements.bridgeStatus.innerHTML =
        '<span class="status-dot"></span><span>Connection error</span>';
      elements.submitHelp.textContent = "Restart the app.";
      showError({
        message: "Could not connect to the app's Python process.",
        hint: String(error),
      });
    }
  }

  function syncSummaryOptions() {
    const enabled = elements.summary.checked;
    elements.summaryOptions.classList.toggle("hidden", !enabled);
    elements.summaryOptions.setAttribute("aria-hidden", String(!enabled));
    elements.summary.setAttribute("aria-expanded", String(enabled));
    if (!enabled) clearApiKeyError();
    updateExecutionSummary();
    syncActionState();
  }

  function renderConfigurationSources() {
    const apiKeyVariable = state.appInfo.api_key_environment_variable || "GEMINI_API_KEY";
    const modelVariable = state.appInfo.gemini_model_environment_variable || "GEMINI_MODEL";
    const model = state.appInfo.gemini_model || "gemini-flash-lite-latest";

    elements.apiKeySource.className = state.appInfo.api_key_configured
      ? "config-source config-source-ready"
      : "config-source config-source-missing";

    if (state.appInfo.api_key_configured) {
      elements.apiKeySourceTitle.textContent = `Using environment variable ${apiKeyVariable}`;
      elements.apiKeySourceDescription.textContent =
        "The key is hidden. Enter another key below to override it for this run only.";
      elements.apiKeyLabel.textContent = "Override with another Gemini API key (optional)";
      elements.apiKey.placeholder = "Enter another API key only if needed";
      elements.apiKeyNote.textContent =
        `Leave this blank to use ${apiKeyVariable}. Entered values are never saved.`;
    } else {
      elements.apiKeySourceTitle.textContent = "Gemini API key is not configured";
      elements.apiKeySourceDescription.textContent =
        "To create a summary, enter a key issued by Google AI Studio below.";
      elements.apiKeyLabel.textContent = "Gemini API key (required for summarization)";
      elements.apiKey.placeholder = "Enter a Gemini API key";
      elements.apiKeyNote.textContent = "The value is never saved and is used only for this run.";
    }

    elements.geminiModelSource.textContent = state.appInfo.gemini_model_source === "environment"
      ? `Current setting: ${modelVariable} = ${model}`
      : `Current setting: app default = ${model}`;
  }

  function updateExecutionSummary() {
    const format = elements.transcriptFormat.options[elements.transcriptFormat.selectedIndex].text;
    const parts = [
      `Transcript: ${format}`,
      "Captions: original language",
    ];
    if (elements.summary.checked) {
      const summaryLanguage =
        elements.summaryLanguage.options[elements.summaryLanguage.selectedIndex].text;
      parts.push(`Summary: ${summaryLanguage}`);
    } else {
      parts.push("Summary: off");
    }
    if (elements.cookieBrowser.value) {
      const browser = elements.cookieBrowser.options[elements.cookieBrowser.selectedIndex].text;
      parts.push(`Cookies: ${browser}`);
    }
    elements.runSummary.textContent = parts.join(" / ");
  }

  function syncActionState() {
    const hasUrl = Boolean(elements.videoUrl.value.trim());
    elements.extractButton.disabled = state.busy || !state.bridgeReady || !hasUrl;

    if (!state.bridgeReady) {
      elements.submitHelp.textContent = "Preparing the app.";
    } else if (!hasUrl) {
      elements.submitHelp.textContent = "Enter a YouTube video to get started.";
    } else if (elements.summary.checked) {
      elements.submitHelp.textContent = "A Gemini summary will be created after the transcript.";
    } else {
      elements.submitHelp.textContent = "Only the transcript will be created.";
    }

    if (!state.busy) {
      elements.extractButtonLabel.textContent = elements.summary.checked
        ? "Create transcript and summary"
        : "Create transcript";
    }
  }

  function toggleApiKeyVisibility() {
    const reveal = elements.apiKey.type === "password";
    elements.apiKey.type = reveal ? "text" : "password";
    elements.apiKeyVisibilityButton.textContent = reveal ? "Hide" : "Show";
    elements.apiKeyVisibilityButton.setAttribute("aria-pressed", String(reveal));
    elements.apiKey.focus();
  }

  function switchFormTab(tab) {
    if (!["execute", "settings"].includes(tab) || state.busy) {
      return;
    }
    state.activeFormTab = tab;
    document.querySelectorAll("[data-form-tab]").forEach((button) => {
      const active = button.dataset.formTab === tab;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
    });
    elements.executeFormPanel.classList.toggle("hidden", tab !== "execute");
    elements.settingsFormPanel.classList.toggle("hidden", tab !== "settings");
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (!state.bridgeReady || state.busy) {
      return;
    }

    const url = elements.videoUrl.value.trim();
    if (!url) {
      switchFormTab("execute");
      setUrlError("Enter a YouTube URL or video ID.");
      return;
    }
    clearApiKeyError();
    if (
      elements.summary.checked &&
      !state.appInfo.api_key_configured &&
      !elements.apiKey.value.trim()
    ) {
      setApiKeyError(
        "Enter a Gemini API key or set the GEMINI_API_KEY environment variable.",
      );
      switchFormTab("settings");
      elements.apiKey.focus();
      return;
    }
    if (elements.summary.checked && !elements.geminiModel.value.trim()) {
      switchFormTab("settings");
      elements.geminiModel.focus();
      showToast("Enter the Gemini model ID to use for summarization.", "error");
      return;
    }

    setBusy(true);
    hideError();
    elements.resultPanel.classList.add("hidden");
    elements.progressPanel.classList.remove("hidden");
    window.App.onProgress({ percent: 2, message: "Starting…" });

    const payload = {
      url,
      transcript_format: elements.transcriptFormat.value,
      generate_summary: elements.summary.checked,
      summary_language: elements.summaryLanguage.value,
      long_summary_mode: "ask",
      cookie_browser: elements.cookieBrowser.value,
      api_key: elements.apiKey.value.trim(),
      gemini_model: elements.geminiModel.value.trim(),
    };

    try {
      const response = await window.pywebview.api.extract(payload);
      if (!response || !response.ok) {
        showError(response && response.error ? response.error : {});
        return;
      }
      renderResult(response.result);
      showToast("Transcript complete.", "success");
    } catch (error) {
      showError({
        message: "Communication with the Python process failed.",
        hint: error && error.message ? error.message : String(error),
      });
    } finally {
      elements.progressPanel.classList.add("hidden");
      setBusy(false);
    }
  }

  function setBusy(busy) {
    state.busy = busy;
    elements.extractButton.classList.toggle("is-busy", busy);
    if (busy) {
      elements.extractButtonLabel.textContent = "Processing…";
      elements.apiKey.type = "password";
      elements.apiKeyVisibilityButton.textContent = "Show";
      elements.apiKeyVisibilityButton.setAttribute("aria-pressed", "false");
    }

    [
      elements.executeFormTab,
      elements.settingsFormTab,
      elements.videoUrl,
      elements.transcriptFormat,
      elements.summary,
      elements.summaryLanguage,
      elements.cookieBrowser,
      elements.apiKey,
      elements.apiKeyVisibilityButton,
      elements.geminiModel,
    ].forEach((control) => {
      control.disabled = busy;
    });
    document.querySelectorAll("[data-summary-mode]").forEach((button) => {
      button.disabled = busy;
    });
    syncActionState();
  }

  function renderResult(result) {
    state.result = result;
    state.activeTab = "transcript";
    elements.resultTitle.textContent = result.video_title || result.video_id;

    const duration = formatDuration(result.duration);
    const size = String(result.language || "").toLowerCase().startsWith("ja")
      ? `${Number(result.character_count || 0).toLocaleString()} characters`
      : `${Number(result.word_count || 0).toLocaleString()} words`;
    elements.resultMeta.textContent = `${duration} ・ ${result.caption_label} ・ ${size}`;

    elements.warningBanner.classList.toggle("hidden", !result.warning);
    elements.warningBanner.textContent = result.warning || "";
    const hasSummary = Boolean(result.summary);
    elements.summaryActionGroup.classList.toggle("hidden", !hasSummary);
    elements.combinedResultActions.classList.toggle("hidden", !hasSummary);
    elements.transcriptFormatBadge.textContent = String(result.transcript.format || "md")
      .toUpperCase();

    const summaryLimit = result.summary_limit;
    const needsSummaryChoice = Boolean(summaryLimit && summaryLimit.requires_confirmation);
    elements.summaryLimitPanel.classList.toggle("hidden", !needsSummaryChoice);
    if (needsSummaryChoice) {
      const source = Number(summaryLimit.source_characters || 0).toLocaleString();
      const limit = Number(summaryLimit.limit_characters || 0).toLocaleString();
      elements.summaryLimitMessage.textContent =
        `Caption length: [${source} / ${limit} characters]. Choose how Gemini should summarize it.`;
    }
    switchTab("transcript");
    elements.resultPanel.classList.remove("hidden");
    elements.resultPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function switchTab(tab) {
    if (!state.result || (tab === "summary" && !state.result.summary)) {
      return;
    }
    state.activeTab = tab;
    document.querySelectorAll("[data-tab]").forEach((button) => {
      const active = button.dataset.tab === tab;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    const artifact = tab === "summary" ? state.result.summary : state.result.transcript;
    const content = artifact ? artifact.content : "";
    const isMarkdown = artifact && artifact.format === "md";
    elements.markdownOutput.classList.toggle("plain-output", !isMarkdown);
    if (isMarkdown) {
      elements.markdownOutput.innerHTML = renderMarkdown(content);
    } else {
      elements.markdownOutput.textContent = content;
    }
    elements.markdownOutput.setAttribute(
      "aria-label",
      tab === "summary" ? "Summary preview" : "Transcript preview",
    );
  }

  async function resolveLongSummary(mode) {
    if (!state.result || state.busy || !["truncate", "full", "skip"].includes(mode)) return;
    setBusy(true);
    hideError();
    elements.progressPanel.classList.remove("hidden");
    window.App.onProgress({ percent: 72, message: "Applying summary choice…" });
    try {
      const response = await window.pywebview.api.summarize_latest(
        mode,
        elements.apiKey.value.trim(),
        elements.summaryLanguage.value,
        elements.geminiModel.value.trim(),
      );
      if (!response || !response.ok) {
        showError(response && response.error ? response.error : {});
        return;
      }
      renderResult(response.result);
      if (response.result.summary) {
        switchTab("summary");
        showToast("Summary complete.", "success");
      } else if (mode === "skip") {
        showToast("Summary skipped.", "success");
      } else {
        showToast("Summary failed. Choose another option or review the warning.", "error");
      }
    } catch (error) {
      showError({
        message: "Communication with the Python process failed.",
        hint: error && error.message ? error.message : String(error),
      });
    } finally {
      elements.progressPanel.classList.add("hidden");
      setBusy(false);
    }
  }

  async function saveResult(kind, button) {
    if (!getArtifact(kind)) return;
    button.disabled = true;
    try {
      const response = await window.pywebview.api.save_result(kind);
      if (!response.ok) {
        showToast(response.error || "Could not save the file.", "error");
      } else if (!response.cancelled) {
        showToast(`Saved to: ${response.path}`, "success");
      }
    } catch (error) {
      showToast(`Could not save the file: ${error}`, "error");
    } finally {
      button.disabled = false;
    }
  }

  async function saveBothResults() {
    if (!state.result || !state.result.summary) return;
    elements.saveBothButton.disabled = true;
    try {
      let response = await window.pywebview.api.save_all_results(false);
      if (response && response.needs_overwrite_confirmation) {
        const names = (response.conflicts || []).join("\n");
        if (!window.confirm(`The following files already exist:\n\n${names}\n\nReplace them?`)) {
          return;
        }
        response = await window.pywebview.api.save_all_results(true);
      }
      if (!response || !response.ok) {
        showToast((response && response.error) || "Could not save the files.", "error");
      } else if (!response.cancelled) {
        showToast(`Saved ${response.paths.length} files.`, "success");
      }
    } catch (error) {
      showToast(`Could not save the files: ${error}`, "error");
    } finally {
      elements.saveBothButton.disabled = false;
    }
  }

  function getArtifact(kind) {
    if (!state.result || !["transcript", "summary"].includes(kind)) return null;
    return kind === "summary" ? state.result.summary : state.result.transcript;
  }

  async function copyResult(kind) {
    const artifact = getArtifact(kind);
    if (!artifact) return;
    const content = artifact.content;
    try {
      await navigator.clipboard.writeText(content);
    } catch (_error) {
      const textarea = document.createElement("textarea");
      textarea.value = content;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      textarea.remove();
    }
    const label = kind === "summary" ? "Summary" : "Transcript";
    showToast(`${label} copied to the clipboard.`, "success");
  }

  async function openCurrentVideo() {
    try {
      const response = await window.pywebview.api.open_video();
      if (!response.ok) showToast(response.error || "Could not open the video.", "error");
    } catch (error) {
      showToast(`Could not open the video: ${error}`, "error");
    }
  }

  async function handleOutputLink(event) {
    const link = event.target.closest("[data-video-seconds]");
    if (!link) return;
    event.preventDefault();
    try {
      const response = await window.pywebview.api.open_video_at(link.dataset.videoSeconds);
      if (!response.ok) showToast(response.error || "Could not open the timestamp.", "error");
    } catch (error) {
      showToast(`Could not open the timestamp: ${error}`, "error");
    }
  }

  function showError(error) {
    elements.errorMessage.textContent = error.message || "An unexpected error occurred.";
    elements.errorHint.textContent = error.hint || "Check the settings, then try again.";
    elements.errorPanel.classList.remove("hidden");
    elements.errorPanel.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function hideError() {
    elements.errorPanel.classList.add("hidden");
  }

  function setUrlError(message) {
    elements.urlError.textContent = message;
    elements.urlError.classList.remove("hidden");
    elements.videoUrl.setAttribute("aria-invalid", "true");
    elements.videoUrl.focus();
  }

  function clearUrlError() {
    elements.urlError.classList.add("hidden");
    elements.urlError.textContent = "";
    elements.videoUrl.removeAttribute("aria-invalid");
  }

  function setApiKeyError(message) {
    elements.apiKeyError.textContent = message;
    elements.apiKeyError.classList.remove("hidden");
    elements.apiKey.setAttribute("aria-invalid", "true");
  }

  function clearApiKeyError() {
    elements.apiKeyError.classList.add("hidden");
    elements.apiKeyError.textContent = "";
    elements.apiKey.removeAttribute("aria-invalid");
  }

  function showToast(message, type = "info") {
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    elements.toastRegion.appendChild(toast);
    window.setTimeout(() => toast.remove(), 3800);
  }

  function formatDuration(seconds) {
    const total = Math.max(0, Math.floor(Number(seconds) || 0));
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const secs = total % 60;
    return [hours, minutes, secs].map((value) => String(value).padStart(2, "0")).join(":");
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function renderInline(value) {
    const codeTokens = [];
    const linkTokens = [];
    let raw = String(value).replace(
      /\[([^\]]+)\]\((https:\/\/www\.youtube\.com\/watch\?[^)\s]+)\)/g,
      (_match, label, url) => {
        const token = `\u0000LINK${linkTokens.length}\u0000`;
        linkTokens.push(renderYouTubeLink(label, url));
        return token;
      },
    );
    let text = escapeHtml(raw);
    text = text.replace(/`([^`]+)`/g, (_match, code) => {
      const token = `\u0000CODE${codeTokens.length}\u0000`;
      codeTokens.push(`<code>${code}</code>`);
      return token;
    });
    text = text.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    text = text.replace(/__([^_]+)__/g, "<strong>$1</strong>");
    text = text.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    text = text.replace(/\u0000CODE(\d+)\u0000/g, (_match, index) => codeTokens[Number(index)]);
    text = text.replace(/\u0000LINK(\d+)\u0000/g, (_match, index) => linkTokens[Number(index)]);
    return text;
  }

  function renderYouTubeLink(label, value) {
    try {
      const url = new URL(value);
      if (url.protocol !== "https:" || url.hostname !== "www.youtube.com") return escapeHtml(label);
      const seconds = Math.max(0, Number.parseInt(url.searchParams.get("t") || "0", 10) || 0);
      return `<a href="#" data-video-seconds="${seconds}">${escapeHtml(label)}</a>`;
    } catch (_error) {
      return escapeHtml(label);
    }
  }

  function renderMarkdown(markdown) {
    const lines = String(markdown).replace(/\r\n?/g, "\n").split("\n");
    const output = [];
    let paragraph = [];
    let listType = null;

    const flushParagraph = () => {
      if (!paragraph.length) return;
      output.push(`<p>${paragraph.map(renderInline).join("<br>")}</p>`);
      paragraph = [];
    };
    const closeList = () => {
      if (listType) output.push(`</${listType}>`);
      listType = null;
    };

    for (let index = 0; index < lines.length; index += 1) {
      const raw = lines[index];
      const line = raw.trim();

      if (line.startsWith("```")) {
        flushParagraph();
        closeList();
        const code = [];
        index += 1;
        while (index < lines.length && !lines[index].trim().startsWith("```")) {
          code.push(lines[index]);
          index += 1;
        }
        output.push(`<pre><code>${escapeHtml(code.join("\n"))}</code></pre>`);
        continue;
      }

      const heading = line.match(/^(#{1,4})\s+(.+)$/);
      if (heading) {
        flushParagraph();
        closeList();
        const level = heading[1].length;
        output.push(`<h${level}>${renderInline(heading[2])}</h${level}>`);
        continue;
      }

      if (/^(-{3,}|\*{3,}|_{3,})$/.test(line)) {
        flushParagraph();
        closeList();
        output.push("<hr>");
        continue;
      }

      const unordered = line.match(/^[-+*]\s+(.+)$/);
      const ordered = line.match(/^\d+[.)]\s+(.+)$/);
      if (unordered || ordered) {
        flushParagraph();
        const nextType = unordered ? "ul" : "ol";
        if (listType !== nextType) {
          closeList();
          output.push(`<${nextType}>`);
          listType = nextType;
        }
        output.push(`<li>${renderInline((unordered || ordered)[1])}</li>`);
        continue;
      }

      if (line.startsWith(">")) {
        flushParagraph();
        closeList();
        const quote = [];
        while (index < lines.length && lines[index].trim().startsWith(">")) {
          quote.push(lines[index].trim().replace(/^>\s?/, ""));
          index += 1;
        }
        index -= 1;
        output.push(`<blockquote>${quote.map(renderInline).join("<br>")}</blockquote>`);
        continue;
      }

      if (!line) {
        flushParagraph();
        closeList();
        continue;
      }

      closeList();
      paragraph.push(line);
    }

    flushParagraph();
    closeList();
    return output.join("\n");
  }
})();
