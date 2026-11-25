// Annotations use the key the repository stores, also when the uploader lists another Unicode form.
import assert from "node:assert/strict";
import { test } from "node:test";
import { storedKey, suggestType } from "../oarepo_pgd/theme/assets/semantic-ui/js/oarepo_pgd/logic.mjs";

const decomposed = "café.txt"; // "café.txt" with a separate accent, as macOS may send it
const composed = decomposed.normalize(); // how the uploader lists it
const link = (key) => ({ self: `https://repo.example/api/datasets/abc-123/draft/files/${encodeURIComponent(key)}` });

test("a file uploaded in the form is annotated under the key the repository stores", () => {
  assert.notEqual(composed, decomposed);
  assert.equal(storedKey(composed, link(decomposed)), decomposed);
});

test("a query or fragment in the link does not hide the stored key", () => {
  const { self } = link(decomposed);
  assert.equal(storedKey(composed, { self: `${self}?download=1` }), decomposed);
  assert.equal(storedKey(composed, { self: `${self}#top` }), decomposed);
});

test("a file listed by its stored key keeps it", () => {
  assert.equal(storedKey(composed, link(composed)), composed);
  assert.equal(storedKey("interview.txt", link("interview.txt")), "interview.txt");
});

test("a stored key with a slash is kept, although its link ends with the last part only", () => {
  // Files already on the draft are listed by their stored key; the link's path keeps the slash.
  const links = { self: "https://repo.example/api/datasets/abc-123/draft/files/raw/interview.txt" };
  assert.equal(storedKey("raw/interview.txt", links), "raw/interview.txt");
});

test("a file without a usable link keeps its listed name", () => {
  assert.equal(storedKey(composed, null), composed);
  assert.equal(storedKey(composed, {}), composed);
  assert.equal(storedKey(composed, { self: "https://repo.example/files/%E0%A4%A" }), composed);
  // A link to another file is not taken over.
  assert.equal(storedKey(composed, link("other.txt")), composed);
});

test("filename patterns match every Unicode form of a name", () => {
  const profile = { semantic_types: [{ id: "menu", filename_patterns: [`${composed.slice(0, 4)}*`] }] };
  assert.equal(suggestType(profile, decomposed), "menu");
  assert.equal(suggestType(profile, composed), "menu");
  const decomposedPattern = { semantic_types: [{ id: "menu", filename_patterns: ["café*"] }] };
  assert.equal(suggestType(decomposedPattern, composed), "menu");
});

test("equivalent patterns of two types are equally specific and leave the choice to the depositor", () => {
  const profile = {
    semantic_types: [
      { id: "menu", filename_patterns: [`${composed.slice(0, 4)}*`] },
      { id: "receipt", filename_patterns: ["cafe\u0301*"] },
    ],
  };
  assert.equal(suggestType(profile, composed), undefined);
});
