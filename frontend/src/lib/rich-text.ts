/**
 * Parser mínimo de Markdown para as respostas do assistente.
 *
 * A IA costuma responder com `**negrito**`, listas e links. Em vez de exibir os
 * marcadores crus, este módulo converte o texto em uma árvore de blocos/spans
 * que o componente `RichText` renderiza como JSX (sem `dangerouslySetInnerHTML`).
 */

export type Inline =
  | { kind: "text"; text: string }
  | { kind: "bold"; text: string }
  | { kind: "italic"; text: string }
  | { kind: "code"; text: string }
  | { kind: "link"; text: string; href: string };

export type Block =
  | { kind: "paragraph"; spans: Inline[] }
  | { kind: "heading"; spans: Inline[] }
  | { kind: "list"; ordered: boolean; items: Inline[][] }
  | { kind: "code"; text: string };

// Ordem importa: negrito antes de itálico para `**texto**` não virar `*` + `*`.
const INLINE_PATTERN = /(\*\*[^*\n]+\*\*|\*[^*\n]+\*|`[^`\n]+`|\[[^\]\n]+\]\(https?:\/\/[^\s)]+\))/g;
const LINK_PATTERN = /^\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)$/;

function parseInline(line: string): Inline[] {
  const spans: Inline[] = [];
  for (const part of line.split(INLINE_PATTERN)) {
    if (!part) continue;

    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      spans.push({ kind: "bold", text: part.slice(2, -2) });
      continue;
    }
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
      spans.push({ kind: "code", text: part.slice(1, -1) });
      continue;
    }
    if (part.startsWith("[")) {
      const match = LINK_PATTERN.exec(part);
      if (match) {
        spans.push({ kind: "link", text: match[1], href: match[2] });
        continue;
      }
    }
    if (part.startsWith("*") && part.endsWith("*") && part.length > 2) {
      spans.push({ kind: "italic", text: part.slice(1, -1) });
      continue;
    }

    // Sobras de `**` (marcador sem par) não devem aparecer na resposta.
    const text = part.replace(/\*\*/g, "");
    if (text) spans.push({ kind: "text", text });
  }
  return spans;
}

const BULLET = /^\s*[-*•]\s+(.*)$/;
const ORDERED = /^\s*\d+[.)]\s+(.*)$/;
const HEADING = /^\s*#{1,6}\s+(.*)$/;

export function parseRichText(source: string): Block[] {
  const lines = source.replace(/\r\n?/g, "\n").split("\n");
  const blocks: Block[] = [];

  let list: { ordered: boolean; items: Inline[][] } | null = null;
  let code: string[] | null = null;

  const flushList = () => {
    if (list && list.items.length > 0) {
      blocks.push({ kind: "list", ordered: list.ordered, items: list.items });
    }
    list = null;
  };

  for (const line of lines) {
    if (line.trimStart().startsWith("```")) {
      if (code === null) {
        flushList();
        code = [];
      } else {
        blocks.push({ kind: "code", text: code.join("\n") });
        code = null;
      }
      continue;
    }
    if (code !== null) {
      code.push(line);
      continue;
    }

    const bullet = BULLET.exec(line);
    const ordered = bullet ? null : ORDERED.exec(line);

    if (bullet || ordered) {
      const orderedList = Boolean(ordered);
      if (list && list.ordered !== orderedList) flushList();
      list ??= { ordered: orderedList, items: [] };
      list.items.push(parseInline((bullet ?? ordered)![1]));
      continue;
    }

    flushList();

    if (!line.trim()) continue;

    const heading = HEADING.exec(line);
    if (heading) {
      blocks.push({ kind: "heading", spans: parseInline(heading[1]) });
      continue;
    }

    blocks.push({ kind: "paragraph", spans: parseInline(line) });
  }

  if (code !== null && code.length > 0) {
    blocks.push({ kind: "code", text: code.join("\n") });
  }
  flushList();

  return blocks;
}
