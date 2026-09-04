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
