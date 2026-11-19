// Automatic annotation changes when the uploaded files change.
import assert from "node:assert/strict";
import { test } from "node:test";
import { reconcileAnnotations } from "../oarepo_pgd/theme/assets/semantic-ui/js/oarepo_pgd/logic.mjs";

const profile = {
  id: "recorded-interview",
  semantic_types: [
    { id: "interview-recording", filename_patterns: ["*.wav"] },
    { id: "interview-transcript", filename_patterns: ["interview.txt"] },
  ],
};
const recording = { file_key: "interview.wav", semantic_types: ["interview-recording"] };
// A manual assignment that differs from what the filename would suggest.
const manual = { file_key: "interview.txt", semantic_types: ["interview-recording"], description: "Edited" };

test("a deletion and a completed upload in one change give one consistent update", () => {
  const next = reconcileAnnotations([recording, manual], {
    deleted: ["interview.wav"],
    keys: ["interview.txt", "second.wav"],
    profile,
  });
  assert.deepEqual(next, [manual, { file_key: "second.wav", semantic_types: ["interview-recording"] }]);
});

test("manual assignments and stale annotations from loading are kept", () => {
  const stale = { file_key: "removed-elsewhere.wav", semantic_types: ["interview-recording"] };
  const annotations = [manual, stale];
  assert.equal(reconcileAnnotations(annotations, { keys: ["interview.txt"], profile }), annotations);
});

test("files without a matching pattern and without a profile get no suggestion", () => {
  assert.deepEqual(reconcileAnnotations([], { keys: ["notes.md"], profile }), []);
  const annotations = [recording];
  assert.equal(reconcileAnnotations(annotations, { keys: ["interview.wav", "new.wav"], profile: null }), annotations);
});

test("a deletion alone removes only that annotation", () => {
  assert.deepEqual(
    reconcileAnnotations([recording, manual], { deleted: ["interview.wav"], keys: ["interview.txt"], profile }),
    [manual],
  );
});
