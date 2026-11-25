import React, { useEffect, useRef } from "react";
import PropTypes from "prop-types";
import { useFormikContext } from "formik";
import Overridable from "react-overridable";
import { buildUID } from "react-searchkit";
import { Message } from "semantic-ui-react";
import { useFormConfig } from "@js/oarepo_ui/forms";
import { useDepositionCheck } from "./hooks";
import { t } from "@translations/oarepo_pgd";
import { FileAssignments } from "./FileAssignments";
import { annotationEditor, reconcileAnnotations } from "./logic.mjs";
import { ProfileSelector } from "./ProfileSelector";
import { RequirementCards } from "./RequirementCards";
import { SemanticDefinitions } from "./SemanticDefinitions";

/**
 * Files section with profile selection, requirement cards and file meanings around the standard uploader.
 *
 * The four parts are overridable under the form's prefix, e.g. `Datasets.Form.ProfileFields.RequirementCards`.
 * A replacement receives the same props as the plugin's component, so it changes the markup and keeps the logic.
 */
export function ProfileFields({ record, uploader }) {
  const { setFieldValue } = useFormikContext();
  const { overridableIdPrefix } = useFormConfig();
  const uid = (part) => buildUID(overridableIdPrefix, `ProfileFields.${part}`);
  const { configuration, metadata, filesEnabled, present, keys, result } = useDepositionCheck(record);
  const selected = metadata.pgd_deposition_profile;
  const annotations = metadata.pgd_file_annotations ?? [];
  const profile = configuration?.profiles.find(
    (item) => item.id === selected?.id && item.revision === selected?.revision,
  );
  // The form's values change only on its next render, so writes also go to a
  // ref; successive edits in one event then build on each other.
  const latest = useRef(annotations);
  latest.current = annotations;
  const setAnnotations = (value) => {
    latest.current = value;
    setFieldValue("metadata.pgd_file_annotations", value);
  };
  const onAnnotationChange = annotationEditor(() => latest.current, setAnnotations);

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
    const next = reconcileAnnotations(latest.current, { deleted, keys, profile });
    if (next !== latest.current) setAnnotations(next);
  }, [[...present].join("\0"), keys.join("\0"), annotations, profile]);

  // Profile controls only for a record with files and a model with profiles.
  const controls = filesEnabled && configuration?.profiles.length > 0;
  const types = new Map((configuration?.semantic_types ?? []).map((type) => [type.id, type]));

  // One tree for every state, with the uploader always in the same place:
  // switching a record to metadata-only and back must not remount the
  // uploader, which would drop files selected but not yet uploading.
  return (
    <section className="profile-guided">
      {controls && (
        <>
          <h2>{t("Describe files with a profile")}</h2>
          <p>{t("Choose a deposition profile, upload your files, and review their meanings. You can save your draft and continue later.")}</p>
          <Overridable id={uid("ProfileSelector")}>
            <ProfileSelector
              profiles={configuration.profiles}
              value={profile?.id ?? ""}
              onChange={(value) => {
                const choice = configuration.profiles.find((item) => item.id === value);
                setFieldValue("metadata.pgd_deposition_profile", choice ? { id: choice.id, revision: choice.revision } : {});
              }}
            />
          </Overridable>
          {selected?.id && !profile && (
            <Message negative role="alert">
              {t("This draft uses a profile version that is no longer available. Select a profile and review the file meanings.")}
            </Message>
          )}
          {profile && (
            <Overridable id={uid("RequirementCards")}>
              <RequirementCards profile={profile} types={types} counts={result.counts} />
            </Overridable>
          )}
          <h3 className="rel-mt-2">{t("Upload files")}</h3>
        </>
      )}
      {filesEnabled && !configuration && (
        <Message negative role="alert">
          {t("The deposition profiles are missing from this form's configuration, so file requirements cannot be checked.")}
        </Message>
      )}
      {uploader}
      {controls && profile && (
        <>
          <Overridable id={uid("FileAssignments")}>
            <FileAssignments configuration={configuration} profile={profile} types={types} keys={keys}
              annotations={annotations} errors={result.errors}
              onAnnotationChange={onAnnotationChange} />
          </Overridable>
          <Overridable id={uid("SemanticDefinitions")}>
            <SemanticDefinitions semanticTypes={configuration.semantic_types} />
          </Overridable>
        </>
      )}
    </section>
  );
}

ProfileFields.propTypes = {
  record: PropTypes.object,
  uploader: PropTypes.node.isRequired,
};
