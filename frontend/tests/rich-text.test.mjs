import assert from "node:assert/strict";
import { test } from "node:test";

import { parseRichText } from "../src/lib/rich-text.ts";

function textOf(spans) {
  return spans.map((span) => span.text).join("");
}

test("negrito da IA é convertido em span e não mostra asteriscos", () => {
  const blocks = parseRichText("O cliente cadastrado no seu escopo é **Bruno de Sousa**.");
  assert.equal(blocks.length, 1);
  assert.equal(blocks[0].kind, "paragraph");
  assert.deepEqual(blocks[0].spans, [
    { kind: "text", text: "O cliente cadastrado no seu escopo é " },
    { kind: "bold", text: "Bruno de Sousa" },
    { kind: "text", text: "." },
  ]);
  assert.equal(textOf(blocks[0].spans), "O cliente cadastrado no seu escopo é Bruno de Sousa.");
});

test("marcador ** sem par é removido do texto", () => {
  const blocks = parseRichText("Valor **solto na resposta");
  assert.equal(textOf(blocks[0].spans), "Valor solto na resposta");
});

test("itálico, código e link são reconhecidos", () => {
  const blocks = parseRichText("Veja *isso*, `codigo` e [a fonte](https://exemplo.com/doc).");
  assert.deepEqual(blocks[0].spans, [
    { kind: "text", text: "Veja " },
    { kind: "italic", text: "isso" },
    { kind: "text", text: ", " },
    { kind: "code", text: "codigo" },
    { kind: "text", text: " e " },
    { kind: "link", text: "a fonte", href: "https://exemplo.com/doc" },
    { kind: "text", text: "." },
  ]);
});

test("listas com marcador e numeradas viram blocos separados", () => {
  const blocks = parseRichText("- um\n- dois\n\n1. primeiro\n2. segundo");
  assert.equal(blocks.length, 2);
  assert.deepEqual(blocks[0], {
    kind: "list",
    ordered: false,
    items: [[{ kind: "text", text: "um" }], [{ kind: "text", text: "dois" }]],
  });
  assert.deepEqual(blocks[1], {
    kind: "list",
    ordered: true,
    items: [[{ kind: "text", text: "primeiro" }], [{ kind: "text", text: "segundo" }]],
  });
});

test("título em Markdown vira heading sem os cerquilhas", () => {
  const blocks = parseRichText("## Resumo");
  assert.equal(blocks[0].kind, "heading");
  assert.equal(textOf(blocks[0].spans), "Resumo");
});

test("bloco de código preserva as linhas e remove as cercas", () => {
  const blocks = parseRichText("```\nlinha 1\nlinha 2\n```");
  assert.deepEqual(blocks, [{ kind: "code", text: "linha 1\nlinha 2" }]);
});
