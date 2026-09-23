import assert from "node:assert/strict";
import { test } from "node:test";

import { initialsOf, roleLabel } from "../src/lib/user-label.ts";

test("roleLabel distingue admin de usuário comum", () => {
  assert.equal(roleLabel("admin"), "Administrador");
  assert.equal(roleLabel("user"), "Usuário");
});

test("initialsOf usa a primeira e a última palavra do nome", () => {
  assert.equal(initialsOf("Bruno de Sousa"), "BS");
  assert.equal(initialsOf("Bruno"), "B");
  assert.equal(initialsOf("  maria   clara  silva "), "MS");
});

test("initialsOf não quebra com nome vazio", () => {
  assert.equal(initialsOf("   "), "?");
  assert.equal(initialsOf(""), "?");
});
