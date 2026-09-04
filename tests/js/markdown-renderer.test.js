"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const assetRoot = path.resolve(__dirname, "../../src/yttext/ui");
const browser = {
  atob(value) {
    return Buffer.from(value, "base64").toString("binary");
  },
  console,
};
browser.globalThis = browser;
browser.window = browser;
vm.createContext(browser);

for (const asset of [
  "markdown-it.min.js",
  "mdit-plugin-tex.min.js",
  "temml.min.js",
  "markdown-renderer.js",
]) {
  vm.runInContext(fs.readFileSync(path.join(assetRoot, asset), "utf8"), browser, {
    filename: asset,
  });
}

const render = browser.YttextMarkdown.render;

test("preserves nested mixed lists and ordered-list numbering", () => {
  const html = render(`1. Encapsulation
   - Use authentication as a boundary

2. Composition
   - Prefer composition to inheritance

3. Exhaustive branching
   - Use enum and match`);

  assert.equal((html.match(/<ol>/g) || []).length, 1);
  assert.match(html, /<li>\s*<p>Encapsulation<\/p>\s*<ul>/);
  assert.match(html, /<\/ul>\s*<\/li>\s*<li>\s*<p>Composition<\/p>/);
  assert.match(html, /<\/ul>\s*<\/li>\s*<li>\s*<p>Exhaustive branching<\/p>/);
  assert.match(render("3. Third\n4. Fourth"), /<ol start="3">/);
});

test("renders the documented Markdown subset", () => {
  const html = render(`###### Detail

| Feature | State |
| --- | --- |
| Tables | **Ready** |

~~Old~~ and [documentation](https://example.com/docs).

\`\`\`js
const marker = "**literal**";
\`\`\``);

  assert.match(html, /<h6>Detail<\/h6>/);
  assert.match(html, /<table>/);
  assert.match(html, /<strong>Ready<\/strong>/);
  assert.match(html, /<s>Old<\/s>/);
  assert.match(
    html,
    /<a href="https:\/\/example\.com\/docs" target="_blank" rel="noopener noreferrer">/,
  );
  assert.match(html, /<code class="language-js">const marker = &quot;\*\*literal\*\*&quot;;/);
});

test("renders bracket-delimited and fenced LaTeX without treating dollars as math", () => {
  const html = render([
    String.raw`Bayes: \(P(A \mid B) = \frac{P(B \mid A)P(A)}{P(B)}\).`,
    "",
    String.raw`\[E = mc^2\]`,
    "",
    "```math",
    String.raw`x = \sqrt{y}`,
    "```",
  ].join("\n"));

  assert.match(html, /<math>/);
  assert.match(html, /<mfrac>/);
  assert.match(html, /<msup>/);
  assert.match(html, /<msqrt>/);
  assert.equal((html.match(/<math display="block"/g) || []).length, 2);

  const literal = render("Price ranges from $10 to $20 and `\\(not math\\)` stays code.");
  assert.doesNotMatch(literal, /<math/);
  assert.match(literal, /\$10 to \$20/);
  assert.ok(literal.includes("<code>\\(not math\\)</code>"));
});

test("escapes raw HTML, rejects unsafe links, and does not load images", () => {
  const html = render(`<script>alert("xss")</script>

[unsafe](javascript:alert(1))

![tracking pixel](https://example.com/pixel.png)`);

  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /href="javascript:/);
  assert.doesNotMatch(html, /<img/);
  assert.match(html, /\[Image: tracking pixel\]/);

  const unsafeMath = render(String.raw`\(\href{javascript:alert(1)}{bad}\)`);
  assert.doesNotMatch(unsafeMath, /<(?:a|script)\b/i);
  assert.doesNotMatch(unsafeMath, /href=/i);
});
