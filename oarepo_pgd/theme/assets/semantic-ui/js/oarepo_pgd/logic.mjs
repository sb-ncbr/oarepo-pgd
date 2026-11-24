// Form-side profile logic, without React or i18next so node can test it.
// checkDeposit mirrors oarepo_pgd/rules.py: keep its rules, messages and their
// order in step with the server check.

function patternExpression(pattern) {
  const escaped = pattern.replace(/[.+?^${}()|[\]\\]/g, "\\$&").replaceAll("*", ".*");
  return new RegExp(`^${escaped}$`, "i");
}

/** The permitted type whose filename pattern matches most specifically, if exactly one does. */
export function suggestType(profile, key) {
  const matches = profile.semantic_types.flatMap((type) =>
    (type.filename_patterns ?? [])
      .filter((pattern) => patternExpression(pattern).test(key))
      .map((pattern) => ({ type, score: pattern.replaceAll("*", "").length })),
  );
  if (!matches.length) return undefined;
  const best = Math.max(...matches.map((match) => match.score));
  const types = new Set(matches.filter((match) => match.score === best).map((match) => match.type.id));
  // Equally specific patterns of different types leave the choice to the depositor.
  return types.size === 1 ? [...types][0] : undefined;
}

/** Compact file-count notation for a requirement: "1+", "2" or "1–3". */
export function countNotation({ min_files: minimum, max_files: maximum }) {
  if (maximum == null) return `${minimum}+`;
  if (minimum === maximum) return `${minimum}`;
  return `${minimum}–${maximum}`;
}

/**
 * How a requirement stands with `count` matching files: "unmet" blocks
 * publication (a required minimum not reached, or any maximum exceeded),
 * "advised" is a recommended minimum not reached, which publication ignores,
 * and "met" is everything else.
 */
export function requirementState(requirement, count) {
  const { level, min_files: minimum, max_files: maximum } = requirement;
  if (maximum != null && count > maximum) return "unmet";
  if (count >= minimum) return "met";
  if (level === "required") return "unmet";
  return level === "recommended" ? "advised" : "met";
}

/**
 * Check annotations against the selected profile.
 *
 * Returns { errors, counts }. Each error is { key, message, params }: `key` is
 * the file the error is about (null for the profile or a requirement),
 * `message` is a catalogue key whose English text is the key itself, and
 * `params` fills its {{placeholders}}. A `count` param selects the plural form.
 * Render errors with errorText(). The English texts must match rules.py; the
 * shared cases in tests/cases/rules.json check that.
 */
export function checkDeposit(configuration, metadata, fileKeys) {
  const errors = [];
  const counts = {};
  const add = (key, message, params = {}) => errors.push({ key, message, params });
  if (!configuration.profiles.length) return { errors, counts };

  const selected = metadata?.deposition_profile ?? {};
  const profile = configuration.profiles.find((item) => item.id === selected.id);
  if (!profile) {
    add(null, "Select a deposition profile.");
    return { errors, counts };
  }
  const name = profile.dataset_category;
  if (selected.revision !== profile.revision) {
    add(null, "{{profile}}: the profile has changed since it was selected. Select it again and review the file meanings.", { profile: name });
  }

  const types = new Map(configuration.semantic_types.map((item) => [item.id, item]));
  const permitted = new Map(profile.semantic_types.map((item) => [item.id, item]));
  const inventory = new Set(fileKeys);

  const annotations = new Map();
  for (const annotation of metadata?.file_annotations ?? []) {
    const key = annotation.file_key;
    // An annotation of a file that is not there is ignored, as on the server.
    if (!inventory.has(key)) continue;
    if (annotations.has(key)) add(key, "the file is annotated more than once. Keep one annotation.");
    else annotations.set(key, annotation);
  }

  for (const key of [...inventory].sort()) {
    const annotation = annotations.get(key) ?? {};
    const assigned = annotation.semantic_types ?? [];
    if (!assigned.length) {
      add(key, "select at least one file meaning.");
      continue;
    }
    if (new Set(assigned).size < assigned.length) add(key, "remove the repeated file meaning.");
    for (const typeId of new Set(assigned)) {
      const label = types.get(typeId)?.label ?? typeId;
      if (!permitted.has(typeId)) {
        add(key, "{{label}} is not a file meaning in the {{profile}} profile.", { label, profile: name });
        continue;
      }
      const formats = permitted.get(typeId).formats;
      if (formats?.length && !formats.some((suffix) => key.toLowerCase().endsWith(`.${suffix.toLowerCase()}`))) {
        add(key, "{{label}} accepts {{formats}} files.", { label, formats: formats.join(", ") });
      }
      if (types.get(typeId)?.requires_description && !(annotation.description ?? "").trim()) {
        add(key, "{{label}} needs a description of what the file is.", { label });
      }
    }
  }

  for (const requirement of profile.requirements) {
    const matching = new Set(requirement.semantic_types);
    const found = [...annotations.values()].filter((annotation) =>
      (annotation.semantic_types ?? []).some((id) => matching.has(id)),
    ).length;
    counts[requirement.id] = found;
    const { label, min_files: minimum, max_files: maximum } = requirement;
    if (requirement.level === "required" && found < minimum) {
      // The help text is repository content, appended as written.
      add(null, "{{label}}: {{found}} of at least {{count}} file.", { label, found, count: minimum, help: requirement.help });
    }
    if (maximum != null && found > maximum) {
      add(null, "{{label}}: {{found}} of at most {{count}} file. Remove or reassign the extra files.", { label, found, count: maximum });
    }
  }
  return { errors, counts };
}

/**
 * The text of an error, rendered with `t(message, params)` (i18next's
 * signature). The requirement's help text is repository content, added as written.
 */
export function messageText(error, t) {
  const { help, ...params } = error.params ?? {};
  return [t(error.message, params), help].filter(Boolean).join(" ");
}

/** The error text prefixed with its file key, as the server reports it. */
export function errorText(error, t) {
  const text = messageText(error, t);
  return error.key == null ? text : `${error.key}: ${text}`;
}

/**
 * The single annotation update for an inventory change.
 *
 * Removes the annotations of files deleted in this session and adds a
 * filename suggestion for each completed file that has no annotation yet.
 * Every other annotation is kept as it is, including manual assignments and
 * annotations of files the draft does not have, which apply once a file of
 * that name is uploaded or imported. Returns `annotations`
 * itself when nothing changes, so the caller can skip the write.
 */
export function reconcileAnnotations(annotations, { deleted = [], keys = [], profile = null }) {
  const removed = new Set(deleted);
  const kept = annotations.filter((item) => !removed.has(item.file_key));
  const annotated = new Set(kept.map((item) => item.file_key));
  const suggestions = profile
    ? keys
        .filter((key) => !removed.has(key) && !annotated.has(key))
        .map((key) => ({ file_key: key, type: suggestType(profile, key) }))
        .filter((item) => item.type)
        .map(({ file_key, type }) => ({ file_key, semantic_types: [type] }))
    : [];
  if (kept.length === annotations.length && !suggestions.length) return annotations;
  return [...kept, ...suggestions];
}

/** The errors for one file, each distinct message once, with a stable key for rendering. */
export function fileAlerts(errors, key) {
  const alerts = new Map();
  for (const error of errors) {
    if (error.key !== key) continue;
    const id = `${error.message}|${JSON.stringify(error.params ?? {})}`;
    if (!alerts.has(id)) alerts.set(id, { id, error });
  }
  return [...alerts.values()];
}
