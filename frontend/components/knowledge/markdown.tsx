import { Fragment, type ReactNode } from "react";

/**
 * Renders the small Markdown subset the knowledge articles use:
 * `#`–`###` headings, paragraphs, `- ` bullet lists and `**bold**`.
 * It builds React elements from text and never injects HTML, so article
 * content can't run scripts in the page.
 */
function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") ? <strong key={i}>{part.slice(2, -2)}</strong> : <Fragment key={i}>{part}</Fragment>
  );
}

export function Markdown({ source }: { source: string }) {
  const blocks: ReactNode[] = [];
  let paragraph: string[] = [];
  let list: string[] = [];

  const flush = () => {
    if (paragraph.length) {
      blocks.push(<p key={blocks.length} className="mt-3 leading-relaxed text-ink">{inline(paragraph.join(" "))}</p>);
      paragraph = [];
    }
    if (list.length) {
      blocks.push(
        <ul key={blocks.length} className="mt-3 list-disc space-y-1.5 ps-5 leading-relaxed text-ink">
          {list.map((item, i) => <li key={i}>{inline(item)}</li>)}
        </ul>
      );
      list = [];
    }
  };

  for (const raw of source.split("\n")) {
    const line = raw.trim();
    const heading = /^(#{1,3})\s+(.*)$/.exec(line);
    if (heading) {
      flush();
      blocks.push(<h2 key={blocks.length} className="mt-6 text-lg font-bold text-ink">{inline(heading[2] ?? "")}</h2>);
    } else if (line.startsWith("- ")) {
      if (paragraph.length) flush();
      list.push(line.slice(2));
    } else if (!line) {
      flush();
    } else {
      if (list.length) flush();
      paragraph.push(line);
    }
  }
  flush();
  return <div className="text-[15px]">{blocks}</div>;
}
