import React, { useEffect, useRef } from "react";
import PropTypes from "prop-types";
import { useFormikContext } from "formik";
import { Form, Message } from "semantic-ui-react";
import { useDepositionCheck } from "./hooks";
import { i18next } from "@translations/oarepo_pgd";
import { FileAssignments } from "./FileAssignments";
import { reconcileAnnotations } from "./logic.mjs";
import { RequirementCards } from "./RequirementCards";

const t = (message, params) => i18next.t(message, params);

/** Files section with profile selection, requirement cards and file meanings around the standard uploader. */
export function ProfileFields({ record, uploader }) {
  const { setFieldValue } = useFormikContext();
  const { configuration, metadata, filesEnabled, present, keys, result } = useDepositionCheck(record);
  const selected = metadata.deposition_profile;
  const annotations = metadata.file_annotations ?? [];
  const profile = configuration?.profiles.find(
    (item) => item.id === selected?.id && item.revision === selected?.revision,
  );
  const setAnnotations = (value) => setFieldValue("metadata.file_annotations", value);

  // One owner for automatic annotation changes: drop annotations of files
  // deleted in this session and suggest meanings for new uploads, as one write.
  // Annotations of files the draft never had in this session stay; they apply
  // once a file of that name arrives, for example when a new version imports
  // the previous version's files.
  const seen = useRef(new Set());
  useEffect(() => {
    const deleted = [...seen.current].filter((key) => !present.has(key));
    keys.forEach((key) => seen.current.add(key));
    deleted.forEach((key) => seen.current.delete(key));
    const next = reconcileAnnotations(annotations, { deleted, keys, profile });
    if (next !== annotations) setAnnotations(next);
  }, [[...present].join("\0"), keys.join("\0"), annotations, profile]);

  if (!filesEnabled || (configuration && !configuration.profiles.length)) return uploader;
  if (!configuration) {
    return (
      <>
        <Message negative role="alert">
          {t("The deposition profiles are missing from this form's configuration, so file requirements cannot be checked.")}
        </Message>
        {uploader}
      </>
    );
  }

  const types = new Map(configuration.semantic_types.map((type) => [type.id, type]));

  return (
    <section className="profile-guided">
      <h2>{t("Describe files with a profile")}</h2>
      <p>{t("Choose a deposition profile, upload your files, and review their meanings. You can save your draft and continue later.")}</p>
      <Form.Dropdown
        // The dropdown is not a native control, so the label names it by reference.
        label={{ id: "deposition-profile-label", children: t("Deposition profile") }}
        aria-labelledby="deposition-profile-label"
        // Shown while nothing is selected; an empty value displays no option text.
        placeholder={t("Select a profile")}
        selection
        // Leaving the field must not select the highlighted profile.
        selectOnBlur={false}
        options={[
          // An empty choice, so the profile can be cleared from the keyboard.
          { key: "", value: "", text: t("Select a profile") },
          ...configuration.profiles.map((item) => ({ key: item.id, value: item.id, text: item.dataset_category })),
        ]}
        value={profile?.id ?? ""}
        onChange={(event, { value }) => {
          const choice = configuration.profiles.find((item) => item.id === value);
          setFieldValue("metadata.deposition_profile", choice ? { id: choice.id, revision: choice.revision } : {});
        }}
      />
      {selected?.id && !profile && (
        <Message negative role="alert">
          {t("This draft uses a profile version that is no longer available. Select a profile and review the file meanings.")}
        </Message>
      )}

      {profile && <RequirementCards profile={profile} types={types} counts={result.counts} />}

      <h3 className="rel-mt-2">{t("Upload files")}</h3>
      {uploader}

      {profile && (
        <>
          <FileAssignments configuration={configuration} profile={profile} types={types} keys={keys}
            annotations={annotations} errors={result.errors} setAnnotations={setAnnotations} />
          <details className="rel-mt-1 rel-mb-1">
            <summary>{t("Semantic definitions")}</summary>
            {configuration.semantic_types.map((type) => (
              <p key={type.id}><strong>{type.label}: </strong>{type.definition}</p>
            ))}
          </details>
        </>
      )}
    </section>
  );
}

ProfileFields.propTypes = {
  record: PropTypes.object,
  uploader: PropTypes.node.isRequired,
};
