// Form-only helpers: filename suggestions, count notation and message rendering.
// The rules themselves are tested against the shared cases in rules.test.mjs.
import assert from "node:assert/strict";
import { test } from "node:test";
import { countNotation, errorText, fileAlerts, requirementState, suggestType } from "../oarepo_pgd/theme/assets/semantic-ui/js/oarepo_pgd/logic.mjs";
import { translator } from "./translator.mjs";

const profile = {
  semantic_types: [
    { id: "site-photo", filename_patterns: ["*.jpg", "*.png"] },
    { id: "field-notebook", filename_patterns: ["*notes*"] },
    { id: "other", filename_patterns: ["*"] },
    { id: "map", filename_patterns: ["*.png"] },
  ],
};

test("suggests the most specific matching type", () => {
  assert.equal(suggestType(profile, "site.JPG"), "site-photo");
  assert.equal(suggestType(profile, "day-notes.txt"), "field-notebook");
  assert.equal(suggestType(profile, "README.md"), "other");
  // Equally specific patterns of two types: the depositor decides.
  assert.equal(suggestType(profile, "area.png"), undefined);
});

test("count notation", () => {
  assert.equal(countNotation({ min_files: 1 }), "1+");
  assert.equal(countNotation({ min_files: 2, max_files: 2 }), "2");
  assert.equal(countNotation({ min_files: 1, max_files: 3 }), "1–3");
});

test("requirement state: only a required minimum or a maximum blocks", () => {
  assert.equal(requirementState({ level: "required", min_files: 1 }, 0), "unmet");
  assert.equal(requirementState({ level: "required", min_files: 1 }, 1), "met");
  assert.equal(requirementState({ level: "recommended", min_files: 1 }, 0), "advised");
  assert.equal(requirementState({ level: "recommended", min_files: 1 }, 1), "met");
  assert.equal(requirementState({ level: "recommended", min_files: 1, max_files: 2 }, 3), "unmet");
  assert.equal(requirementState({ level: "optional", min_files: 0 }, 0), "met");
  assert.equal(requirementState({ level: "optional", min_files: 0, max_files: 1 }, 2), "unmet");
});

test("messages render through a catalogue with plurals and the help text", () => {
  const t = translator({ "{{label}} accepts {{formats}} files.": "{{label}} přijímá soubory {{formats}}." });
  const error = { key: "a.pdf", message: "{{label}} accepts {{formats}} files.", params: { label: "Fotka", formats: "jpg" } };
  assert.equal(errorText(error, t), "a.pdf: Fotka přijímá soubory jpg.");
  const unmet = { key: null, message: "{{label}}: {{found}} of at least {{count}} file.", params: { label: "Photos", found: 0, count: 2, help: "Add photos." } };
  assert.equal(errorText(unmet, translator({ [`${unmet.message}_plural`]: "{{label}}: {{found}} of at least {{count}} files." })),
    "Photos: 0 of at least 2 files. Add photos.");
});

test("file alerts show each distinct error once, with distinct keys", () => {
  const errors = [
    { key: "a.wav", message: "the file is annotated more than once. Keep one annotation.", params: {} },
    { key: "a.wav", message: "the file is annotated more than once. Keep one annotation.", params: {} },
    { key: "a.wav", message: "{{label}} is not a file meaning in the {{profile}} profile.", params: { label: "Map", profile: "Survey" } },
    { key: "a.wav", message: "{{label}} is not a file meaning in the {{profile}} profile.", params: { label: "Photo", profile: "Survey" } },
    { key: "b.txt", message: "select at least one file meaning.", params: {} },
  ];
  const alerts = fileAlerts(errors, "a.wav");
  assert.equal(alerts.length, 3);
  assert.equal(new Set(alerts.map((alert) => alert.id)).size, 3);
  assert.deepEqual(fileAlerts(errors, "c.pdf"), []);
});
