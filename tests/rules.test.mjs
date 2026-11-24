// Form rules against the cases shared with the server (cases/rules.json).
// Messages are rendered with the plugin's English catalogue, as in the form.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { checkDeposit, errorText } from "../oarepo_pgd/theme/assets/semantic-ui/js/oarepo_pgd/logic.mjs";
import { translator } from "./translator.mjs";

const read = (path) => JSON.parse(readFileSync(new URL(path, import.meta.url), "utf-8"));
const shared = read("./cases/rules.json");
const english = translator(read("../oarepo_pgd/theme/assets/semantic-ui/translations/oarepo_pgd/messages/en/translations.json"));

for (const item of shared.cases) {
  test(item.name, () => {
    const metadata = { pgd_deposition_profile: item.profile, pgd_file_annotations: item.annotations };
    const result = checkDeposit(shared.configurations[item.configuration], metadata, item.file_keys);
    assert.deepEqual(result.errors.map((error) => errorText(error, english)), item.errors);
    if (item.counts) assert.deepEqual(result.counts, item.counts);
  });
}
