import React from "react";
import PropTypes from "prop-types";
import { Form } from "semantic-ui-react";
import { i18next } from "@translations/oarepo_pgd";

const t = (message, params) => i18next.t(message, params);

/** Dropdown of the model's profiles; `value` is the selected profile's id or "". */
export function ProfileSelector({ profiles, value, onChange }) {
  return (
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
        ...profiles.map((item) => ({ key: item.id, value: item.id, text: item.dataset_category })),
      ]}
      value={value}
      onChange={(event, data) => onChange(data.value)}
    />
  );
}

ProfileSelector.propTypes = {
  profiles: PropTypes.array.isRequired,
  value: PropTypes.string.isRequired,
  onChange: PropTypes.func.isRequired,
};
