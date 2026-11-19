// Components the plugin registers through OAREPO_UI_OVERRIDES.
import React, { useMemo } from "react";
import PropTypes from "prop-types";
import { TabForm } from "@js/oarepo_ui/forms";
import { withProfiles } from "./sections";

export { ProfilePublishButton } from "./PublishButton";

/**
 * Replaces the tabbed deposit form with the same form whose files section has
 * the profile controls. Working on the section list, not inside the section,
 * lets the tab carry the profile fields' label and error marker.
 */
export function ProfileTabForm({ sections }) {
  // Memoized: a new section component on every render would remount the uploader.
  const profiled = useMemo(() => withProfiles(sections), [sections]);
  return <TabForm sections={profiled} />;
}

ProfileTabForm.propTypes = {
  sections: PropTypes.array.isRequired,
};
