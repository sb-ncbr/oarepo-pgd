import React from "react";
import PropTypes from "prop-types";
import { i18next } from "@translations/oarepo_pgd";

const t = (message, params) => i18next.t(message, params);

/** The definitions of the model's semantic types, folded away by default. */
export function SemanticDefinitions({ semanticTypes }) {
  return (
    <details className="rel-mt-1 rel-mb-1">
      <summary>{t("Semantic definitions")}</summary>
      {semanticTypes.map((type) => (
        <p key={type.id}><strong>{type.label}: </strong>{type.definition}</p>
      ))}
    </details>
  );
}

SemanticDefinitions.propTypes = {
  semanticTypes: PropTypes.array.isRequired,
};
