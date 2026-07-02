/** Minimal markdown → React-friendly blocks (headings, lists, paragraphs). */

export function parseMarkdownLite(text) {
  if (!text) return [];
  const blocks = [];
  const lines = String(text).split("\n");
  let paragraph = [];
  let list = null;

  const flushParagraph = () => {
    if (paragraph.length) {
      blocks.push({ type: "p", text: paragraph.join(" ") });
      paragraph = [];
    }
  };
  const flushList = () => {
    if (list) {
      blocks.push(list);
      list = null;
    }
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    if (!line.trim()) {
      flushParagraph();
      flushList();
      continue;
    }
    if (line.startsWith("## ")) {
      flushParagraph();
      flushList();
      blocks.push({ type: "h2", text: line.slice(3) });
      continue;
    }
    if (line.startsWith("# ")) {
      flushParagraph();
      flushList();
      blocks.push({ type: "h1", text: line.slice(2) });
      continue;
    }
    if (/^[-*]\s+/.test(line)) {
      flushParagraph();
      if (!list) list = { type: "ul", items: [] };
      list.items.push(line.replace(/^[-*]\s+/, ""));
      continue;
    }
    if (/^\d+\.\s+/.test(line)) {
      flushParagraph();
      if (!list || list.type !== "ol") {
        flushList();
        list = { type: "ol", items: [] };
      }
      list.items.push(line.replace(/^\d+\.\s+/, ""));
      continue;
    }
    flushList();
    paragraph.push(line);
  }
  flushParagraph();
  flushList();
  return blocks;
}

export function inlineFormat(text) {
  const parts = [];
  const re = /\*\*([^*]+)\*\*|`([^`]+)`/g;
  let last = 0;
  let match;
  while ((match = re.exec(text)) !== null) {
    if (match.index > last) parts.push({ t: "text", v: text.slice(last, match.index) });
    if (match[1]) parts.push({ t: "strong", v: match[1] });
    if (match[2]) parts.push({ t: "code", v: match[2] });
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push({ t: "text", v: text.slice(last) });
  return parts.length ? parts : [{ t: "text", v: text }];
}
