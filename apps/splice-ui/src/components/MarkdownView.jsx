import { inlineFormat, parseMarkdownLite } from "../utils/markdownLite.js";

function Inline({ text }) {
  return (
    <>
      {inlineFormat(text).map((part, i) => {
        if (part.t === "strong") return <strong key={i}>{part.v}</strong>;
        if (part.t === "code") return <code key={i}>{part.v}</code>;
        return <span key={i}>{part.v}</span>;
      })}
    </>
  );
}

export default function MarkdownView({ text, className = "markdown-view" }) {
  const blocks = parseMarkdownLite(text);
  if (!blocks.length) return <p className="muted">No content.</p>;
  return (
    <div className={className}>
      {blocks.map((block, index) => {
        if (block.type === "h1") {
          return (
            <h3 key={index}>
              <Inline text={block.text} />
            </h3>
          );
        }
        if (block.type === "h2") {
          return (
            <h4 key={index}>
              <Inline text={block.text} />
            </h4>
          );
        }
        if (block.type === "p") {
          return (
            <p key={index}>
              <Inline text={block.text} />
            </p>
          );
        }
        if (block.type === "ul") {
          return (
            <ul key={index}>
              {block.items.map((item, j) => (
                <li key={j}>
                  <Inline text={item} />
                </li>
              ))}
            </ul>
          );
        }
        if (block.type === "ol") {
          return (
            <ol key={index}>
              {block.items.map((item, j) => (
                <li key={j}>
                  <Inline text={item} />
                </li>
              ))}
            </ol>
          );
        }
        return null;
      })}
    </div>
  );
}
