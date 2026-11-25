// The per-file update that the assignments table and its replacements use.
import assert from "node:assert/strict";
import { test } from "node:test";
import { annotationEditor, updateAnnotation } from "../oarepo_pgd/theme/assets/semantic-ui/js/oarepo_pgd/logic.mjs";

const recording = { file_key: "interview.wav", semantic_types: ["interview-recording"], description: "Session 1" };
const transcript = { file_key: "interview.txt", semantic_types: ["interview-transcript"] };

test("a change to one file keeps its other fields, its place and the other annotations", () => {
  const next = updateAnnotation([recording, transcript], "interview.wav", { description: "Session 2" });
  assert.deepEqual(next, [{ ...recording, description: "Session 2" }, transcript]);
});

test("a change to a file without an annotation adds one", () => {
  const next = updateAnnotation([transcript], "notes.pdf", { semantic_types: ["other"] });
  assert.deepEqual(next, [transcript, { file_key: "notes.pdf", semantic_types: ["other"] }]);
});

test("a change to a duplicated file merges into the first annotation and drops the others", () => {
  const duplicate = { file_key: "interview.wav", semantic_types: ["other"] };
  const next = updateAnnotation([recording, transcript, duplicate], "interview.wav", { description: "Session 2" });
  assert.deepEqual(next, [{ ...recording, description: "Session 2" }, transcript]);
});

test("the annotation stays under the given file, also when the changes name another", () => {
  assert.deepEqual(updateAnnotation([recording], "copy.wav", recording), [
    recording,
    { ...recording, file_key: "copy.wav" },
  ]);
  assert.deepEqual(updateAnnotation([recording], "interview.wav", transcript), [
    { ...transcript, description: "Session 1", file_key: "interview.wav" },
  ]);
});

test("the original list is left unchanged", () => {
  const annotations = [recording];
  updateAnnotation(annotations, "interview.wav", { description: "Changed" });
  assert.equal(annotations[0].description, "Session 1");
});

test("two edits before the form re-renders both apply", () => {
  // The written value is visible to the next edit at once; the rendered value is not.
  let latest = [recording, transcript];
  const written = [];
  const edit = annotationEditor(() => latest, (value) => {
    latest = value;
    written.push(value);
  });
  edit("interview.wav", { semantic_types: ["other"] });
  edit("interview.txt", { semantic_types: ["other"] });
  assert.deepEqual(written.at(-1), [
    { ...recording, semantic_types: ["other"] },
    { ...transcript, semantic_types: ["other"] },
  ]);
});
