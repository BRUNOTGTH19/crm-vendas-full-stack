import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { test } from "node:test";

const root = new URL("../", import.meta.url);
const vercel = JSON.parse(readFileSync(new URL("vercel.json", root), "utf8"));
const html = readFileSync(new URL("index.html", root), "utf8");

const entry = vercel.headers.find((rule) => rule.source === "/(.*)");
assert.ok(entry, "vercel.json deve ter a regra global de headers");
const header = entry.headers.find((item) => item.key === "Content-Security-Policy");
assert.ok(header, "a regra global deve enviar Content-Security-Policy");

const directives = new Map(
  header.value
    .split(";")
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => {
      const [name, ...values] = part.split(/\s+/);
      return [name, values];
    })
);

function values(name) {
  return directives.get(name) ?? [];
}

test("script-src permite apenas arquivos da própria origem", () => {
  assert.deepEqual(values("script-src"), ["'self'"]);
  assert.ok(!header.value.includes("'unsafe-eval'"));
});

test("diretivas de bloqueio estão presentes", () => {
  assert.deepEqual(values("object-src"), ["'none'"]);
  assert.deepEqual(values("frame-ancestors"), ["'none'"]);
  assert.deepEqual(values("base-uri"), ["'self'"]);
  assert.deepEqual(values("form-action"), ["'self'"]);
  assert.deepEqual(values("default-src"), ["'self'"]);
});

test("conexões ficam restritas à origem e ao backend", () => {
  const connect = values("connect-src");
  assert.ok(connect.includes("'self'"));
  assert.ok(connect.includes("https://*.onrender.com"));
  assert.ok(!connect.includes("*"));
});

test("index.html não tem script inline", () => {
  const tags = html.match(/<script\b[^>]*>/g) ?? [];
  assert.ok(tags.length > 0);
  for (const tag of tags) {
    assert.match(tag, /\ssrc=/, `script inline bloqueado pela CSP: ${tag}`);
  }
});

test("o tema anti-flash vem de arquivo próprio", () => {
  assert.match(html, /<script src="\/theme-init\.js"><\/script>/);
  const themePath = new URL("public/theme-init.js", root);
  assert.ok(existsSync(themePath));
  const theme = readFileSync(themePath, "utf8");
  assert.match(theme, /crm:theme/);
  assert.doesNotMatch(theme, /^\s*import\s/m);
});
