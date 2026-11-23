import type { ReactNode } from 'react';

// The survey description's formatting, as on the survey link page (respondent
// pages.py): line breaks, **bold**, *italic* or _italic_, and [links](https://…).
const LINK = /\[([^\]\n]+)\]\(((?:https?:\/\/|mailto:)[^\s()"<>]+)\)/;
const BOLD = /\*\*(?=\S)(.+?)(?<=\S)\*\*/;
const ITALIC = /(?<![\w*])\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?![\w*])|(?<!\w)_(?=\S)(.+?)(?<=\S)_(?!\w)/;

/** The help text under description fields. */
export const FORMAT_HINT = 'Line breaks are kept. You can use **bold**, *italic* and [link text](https://example.org).';

function earliest(text: string) {
  // On a tie, the first pattern wins: "**[x](url)**" is bold around a link.
  return [LINK, BOLD, ITALIC]
    .map((pattern) => pattern.exec(text))
    .reduce<RegExpExecArray | null>((best, match) => (match && (!best || match.index < best.index) ? match : best), null);
}

function format(text: string, key: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let rest = text;
  let n = 0;
  for (let match = earliest(rest); match; match = earliest(rest)) {
    if (match.index > 0) nodes.push(rest.slice(0, match.index));
    const id = `${key}.${n++}`;
    if (match[0].startsWith('[')) {
      nodes.push(<a key={id} href={match[2]} target="_blank" rel="noopener noreferrer">{format(match[1], id)}</a>);
    } else if (match[0].startsWith('**')) {
      nodes.push(<strong key={id}>{format(match[1], id)}</strong>);
    } else {
      nodes.push(<em key={id}>{format(match[1] ?? match[2], id)}</em>);
    }
    rest = rest.slice(match.index + match[0].length);
  }
  if (rest) nodes.push(rest);
  return nodes;
}

/** A survey description as respondents see it. Keep line breaks with `white-space: pre-line`. */
export function FormattedText({ text }: { text: string }) {
  return <>{format(text, 'f')}</>;
}
