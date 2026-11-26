// The Czech catalogue translates every form text, with its three plural forms.
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { test } from "node:test";

const root = new URL("../oarepo_pgd/theme/assets/semantic-ui/", import.meta.url);
const source = readdirSync(new URL("js/oarepo_pgd/", root))
  .map((name) => readFileSync(new URL(`js/oarepo_pgd/${name}`, root), "utf-8"))
  .join("\n");
// Texts passed to t(), i18next.t() and the rule checker's add(code, key, message).
const used = new Set(
  [...source.matchAll(/(?:\bt|i18next\.t|add\("\w+",\s*(?:null|key),)\s*\(?\s*"([^"]+)"/g)].map((match) => match[1]),
);
const czech = JSON.parse(readFileSync(new URL("translations/oarepo_pgd/messages/cs/translations.json", root), "utf-8"));
const english = JSON.parse(readFileSync(new URL("translations/oarepo_pgd/messages/en/translations.json", root), "utf-8"));
const plurals = new Set(Object.keys(english).filter((key) => key.endsWith("_plural")).map((key) => key.slice(0, -7)));

test("every form text has a Czech translation", () => {
  const missing = [...used].filter((text) =>
    plurals.has(text) ? !["_0", "_1", "_2"].every((suffix) => czech[text + suffix]) : !czech[text],
  );
  assert.deepEqual(missing, []);
});

test("the Czech catalogue has no texts the form does not use", () => {
  const base = (key) => key.replace(/_[0-2]$/, "");
  assert.deepEqual(Object.keys(czech).map(base).filter((key) => !used.has(key)), []);
});
