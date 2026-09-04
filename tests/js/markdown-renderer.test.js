"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

global.window = {
  markdownit: require("../../src/yttext/ui/markdown-it.min.js"),
};
require("../../src/yttext/ui/markdown-renderer.js");

const render = global.window.YttextMarkdown.render;

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

test("escapes raw HTML, rejects unsafe links, and does not load images", () => {
  const html = render(`<script>alert("xss")</script>

[unsafe](javascript:alert(1))

![tracking pixel](https://example.com/pixel.png)`);

  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /href="javascript:/);
  assert.doesNotMatch(html, /<img/);
  assert.match(html, /\[Image: tracking pixel\]/);
});
