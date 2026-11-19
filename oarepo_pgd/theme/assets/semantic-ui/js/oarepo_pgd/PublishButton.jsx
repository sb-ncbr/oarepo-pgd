import React from "react";
import PropTypes from "prop-types";
import { PublishButton } from "@js/oarepo_ui/forms";
import { i18next } from "@translations/oarepo_pgd";
import { useDepositionCheck } from "./hooks";

const NOTES = {
  unchecked: () => i18next.t("The file requirements cannot be checked, so the deposit cannot be published."),
  unmet: () => i18next.t("Complete the file requirements in Files and meanings before publishing."),
};

/**
 * The standard publish button, disabled until the files are known to meet the
 * selected profile: while requirements are unmet, and when the form has no
 * deposition configuration to check them with. The server check stays authoritative.
 */
export function ProfilePublishButton({ record }) {
  const { configuration, filesEnabled, result } = useDepositionCheck(record);
  let reason = null;
  if (filesEnabled) {
    if (!configuration) reason = "unchecked";
    else if (configuration.profiles.length && result.errors.length) reason = "unmet";
  }
  // Pass `disabled` only when blocked, so the standard button keeps its own conditions otherwise.
  return (
    <div className="publish-button-container profile-guided__publish">
      <PublishButton record={record} {...(reason && { disabled: true })} />
      {reason && <p className="profile-guided__publish-note">{NOTES[reason]()}</p>}
    </div>
  );
}

ProfilePublishButton.propTypes = {
  record: PropTypes.object,
};
