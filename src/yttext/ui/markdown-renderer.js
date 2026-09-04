(() => {
  "use strict";

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  if (typeof window.markdownit !== "function") {
    window.YttextMarkdown = Object.freeze({
      render(markdown) {
        return `<pre class="markdown-fallback">${escapeHtml(markdown ?? "")}</pre>`;
      },
    });
    return;
  }

  const parser = window.markdownit({
    breaks: false,
    html: false,
    linkify: false,
    typographer: false,
  });

  const texPlugin = window.mdItPluginTex?.tex;
  const renderMath = window.temml?.renderToString;

  if (typeof texPlugin === "function" && typeof renderMath === "function") {
    parser.use(texPlugin, {
      delimiters: "brackets",
      mathFence: true,
      render(content, displayMode) {
        try {
          return renderMath(String(content ?? ""), {
            displayMode,
            maxExpand: 1000,
            maxSize: [20, 1000],
            throwOnError: false,
            trust: false,
          });
        } catch (_error) {
          const open = displayMode ? "\\[" : "\\(";
          const close = displayMode ? "\\]" : "\\)";
          return `<code class="math-fallback">${escapeHtml(`${open}${content}${close}`)}</code>`;
        }
      },
    });
  }

  const defaultLinkOpen =
    parser.renderer.rules.link_open ||
    ((tokens, index, options, _environment, renderer) =>
      renderer.renderToken(tokens, index, options));

  parser.renderer.rules.link_open = (tokens, index, options, environment, renderer) => {
    tokens[index].attrSet("target", "_blank");
    tokens[index].attrSet("rel", "noopener noreferrer");
    return defaultLinkOpen(tokens, index, options, environment, renderer);
  };

  // Do not let generated Markdown trigger requests to arbitrary image hosts.
  parser.renderer.rules.image = (tokens, index, options, environment, renderer) => {
    const alt = renderer.renderInlineAsText(tokens[index].children || [], options, environment);
    return `<span class="markdown-image-placeholder">[Image: ${escapeHtml(alt)}]</span>`;
  };

  window.YttextMarkdown = Object.freeze({
    render(markdown) {
      return parser.render(String(markdown ?? ""));
    },
  });
})();
