// Form-side profile logic, without React or i18next so node can test it.
// checkDeposit mirrors oarepo_pgd/rules.py: keep its rules, codes, messages and
// their order in step with the server check.

function patternExpression(pattern) {
  const escaped = pattern.normalize().replace(/[.+?^${}()|[\]\\]/g, "\\$&").replaceAll("*", ".*");
  return new RegExp(`^${escaped}$`, "i");
}

/**
 * The key under which the repository stores a file the uploader lists as `name`.
 *
 * The uploader lists a file uploaded in the open form by the NFC form of its
 * name, which can differ from the stored key: a browser on macOS may send
 * "café.txt" with a separate accent. The last part of the file's own link is
 * the stored key; it is used when it is the same name in another Unicode form.
 * Files already on the draft are listed by their stored key, which may contain "/".
 */
export function storedKey(name, links) {
  if (!links?.self) return name;
  let key;
  try {
    // The path only: a link may carry a query or fragment.
    key = decodeURIComponent(new URL(links.self, "https://localhost").pathname.split("/").pop());
  } catch {
    return name;
  }
  return key && key !== name && key.normalize() === name.normalize() ? key : name;
}

/** The permitted type whose filename pattern matches most specifically, if exactly one does. */
export function suggestType(profile, key) {
  const matches = profile.semantic_types.flatMap((type) =>
    (type.filename_patterns ?? [])
      // Unicode forms of the same name match the same patterns.
      .filter((pattern) => patternExpression(pattern).test(key.normalize()))
      .map((pattern) => ({ type, score: pattern.normalize().replaceAll("*", "").length })),
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
 * and "met" is everything else. The server's requirement_state is the same rule.
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
 * Returns { errors, counts, states }. Each error is
 * { code, key, requirement, message, params }: `code` is the stable code the
 * server's check also reports, `key` the file the error is about and
 * `requirement` the requirement's id (both null when not about one),
 * `message` a catalogue key whose English text is the key itself, and
 * `params` fills its {{placeholders}}. A `count` param selects the plural form.
 * `counts` and `states` are keyed by requirement id; see requirementState().
 * Render errors with errorText(). The codes and English texts must match
 * rules.py; the shared cases in tests/cases/rules.json check that.
 */
export function checkDeposit(configuration, metadata, fileKeys) {
  const errors = [];
  const counts = {};
  const states = {};
  const add = (code, key, message, params = {}, requirement = null) =>
    errors.push({ code, key, requirement, message, params });
  if (!configuration.profiles.length) return { errors, counts, states };

  const selected = metadata?.pgd_deposition_profile ?? {};
  const profile = configuration.profiles.find((item) => item.id === selected.id);
  if (!profile) {
    add("profile_missing", null, "Select a deposition profile.");
    return { errors, counts, states };
  }
  const name = profile.dataset_category;
  if (selected.revision !== profile.revision) {
    add("profile_changed", null, "{{profile}}: the profile has changed since it was selected. Select it again and review the file meanings.", { profile: name });
  }

  const types = new Map(configuration.semantic_types.map((item) => [item.id, item]));
  const permitted = new Map(profile.semantic_types.map((item) => [item.id, item]));
  const inventory = new Set(fileKeys);

  const annotations = new Map();
  for (const annotation of metadata?.pgd_file_annotations ?? []) {
    const key = annotation.file_key;
    // An annotation of a file that is not there is ignored, as on the server.
    if (!inventory.has(key)) continue;
    if (annotations.has(key)) add("annotation_repeated", key, "the file is annotated more than once. Keep one annotation.");
    else annotations.set(key, annotation);
  }

  for (const key of [...inventory].sort()) {
    const annotation = annotations.get(key) ?? {};
    const assigned = annotation.semantic_types ?? [];
    if (!assigned.length) {
      add("meaning_missing", key, "select at least one file meaning.");
      continue;
    }
    if (new Set(assigned).size < assigned.length) add("meaning_repeated", key, "remove the repeated file meaning.");
    for (const typeId of new Set(assigned)) {
      const label = types.get(typeId)?.label ?? typeId;
      if (!permitted.has(typeId)) {
        add("meaning_not_in_profile", key, "{{label}} is not a file meaning in the {{profile}} profile.", { label, profile: name });
        continue;
      }
      const formats = permitted.get(typeId).formats;
      if (formats?.length && !formats.some((suffix) => key.toLowerCase().endsWith(`.${suffix.toLowerCase()}`))) {
        add("format_not_accepted", key, "{{label}} accepts {{formats}} files.", { label, formats: formats.join(", ") });
      }
      if (types.get(typeId)?.requires_description && !(annotation.description ?? "").trim()) {
        add("description_missing", key, "{{label}} needs a description of what the file is.", { label });
      }
    }
  }

  for (const requirement of profile.requirements) {
    const matching = new Set(requirement.semantic_types);
    const found = [...annotations.values()].filter((annotation) =>
      (annotation.semantic_types ?? []).some((id) => matching.has(id)),
    ).length;
    counts[requirement.id] = found;
    states[requirement.id] = requirementState(requirement, found);
    const { label, min_files: minimum, max_files: maximum } = requirement;
    if (requirement.level === "required" && found < minimum) {
      // The help text is repository content, appended as written.
      add("too_few_files", null, "{{label}}: {{found}} of at least {{count}} file.",
        { label, found, count: minimum, help: requirement.help }, requirement.id);
    }
    if (maximum != null && found > maximum) {
      add("too_many_files", null, "{{label}}: {{found}} of at most {{count}} file. Remove or reassign the extra files.",
        { label, found, count: maximum }, requirement.id);
    }
  }
  return { errors, counts, states };
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

/**
 * The annotations with one file's annotation changed.
 *
 * Merges `changes` into the file's first annotation, keeping its other fields
 * and its place in the list, and drops any later annotations of the same file,
 * so an edit also repairs a duplicate. A file without an annotation gets one.
 * The annotation always stays under `key`, whatever `changes` contains.
 */
export function updateAnnotation(annotations, key, changes) {
  const first = annotations.findIndex((item) => item.file_key === key);
  if (first < 0) return [...annotations, { ...changes, file_key: key }];
  return annotations.flatMap((item, index) => {
    if (item.file_key !== key) return [item];
    return index === first ? [{ ...item, ...changes, file_key: key }] : [];
  });
}

/**
 * The `onAnnotationChange(key, changes)` callback of the assignments table.
 *
 * Each edit starts from `current()`, the annotations as last written, so
 * several edits in one event, before the form re-renders, all apply.
 */
export function annotationEditor(current, write) {
  return (key, changes) => write(updateAnnotation(current(), key, changes));
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
