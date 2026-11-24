import React from "react";
import { i18next } from "@translations/oarepo_pgd";
import { ProfileFields } from "./ProfileFields";

const PATHS = ["metadata.pgd_deposition_profile", "metadata.pgd_file_annotations"];

/**
 * Wrap the files section of a section list with the profile controls.
 * The section also takes over the two profile fields, so the form marks its
 * tab when the server reports a profile error.
 */
export function withProfiles(sections, { label = i18next.t("Files and meanings") } = {}) {
  return sections.map((section) =>
    section.key === "files"
      ? {
          ...section,
          label,
          component: (props) => (
            <ProfileFields {...props} uploader={<section.component {...props} />} />
          ),
          includesPaths: [...(section.includesPaths ?? []), ...PATHS],
        }
      : section,
  );
}
