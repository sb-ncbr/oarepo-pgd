import React from "react";
import PropTypes from "prop-types";
import { Card, Icon, Label } from "semantic-ui-react";
import { i18next } from "@translations/oarepo_pgd";
import { countNotation } from "./logic.mjs";

const t = (message, params) => i18next.t(message, params);

const within = (requirement, count) =>
  count >= requirement.min_files && (requirement.max_files == null || count <= requirement.max_files);

/** The selected profile's requirements as cards, with the current file count of each. */
export function RequirementCards({ profile, types, counts }) {
  const required = profile.requirements.filter((requirement) => requirement.level === "required");
  const met = required.filter((requirement) => within(requirement, counts[requirement.id] ?? 0)).length;
  return (
    <>
      <h3 className="rel-mt-2">{t("File requirements")}</h3>
      <p role="status">
        <strong>{t("{{met}}/{{total}} required file counts met", { met, total: required.length })}</strong>
      </p>
      <p>{t("File counts update automatically from the meanings you select.")}</p>
      <Card.Group>
        {profile.requirements.map((requirement) => {
          const total = counts[requirement.id] ?? 0;
          const missing = (requirement.level === "required" && total < requirement.min_files)
            || (requirement.max_files != null && total > requirement.max_files);
          return (
            <Card key={requirement.id} color={missing ? "red" : undefined}>
              <Card.Content>
                <Card.Header>{requirement.label}</Card.Header>
                {requirement.level === "recommended" && <Card.Meta>{t("Recommended")}</Card.Meta>}
                {requirement.help && <Card.Description>{requirement.help}</Card.Description>}
              </Card.Content>
              <Card.Content>
                <Card.Meta>{t("Files")}</Card.Meta>
                <Label.Group>
                  {requirement.semantic_types.map((id) => (
                    <Label key={id} title={types.get(id)?.definition}>{types.get(id)?.label ?? id}</Label>
                  ))}
                  <Label basic title={t("Number of files: {{range}}", { range: countNotation(requirement) })}>
                    {countNotation(requirement)}
                  </Label>
                </Label.Group>
                {requirement.semantic_types.length > 1 && (
                  <Card.Meta>{t("Files with any of these meanings count toward this requirement.")}</Card.Meta>
                )}
              </Card.Content>
              <Card.Content extra>
                {within(requirement, total) && (
                  <Icon name="check" color="green" role="img"
                    aria-label={t("File-count requirement satisfied")} aria-hidden={false} title={t("File-count requirement satisfied")} />
                )}
                {missing && <Icon name="warning circle" color="red" />}
                {t("{{count}} distinct file matching", { count: total })}
              </Card.Content>
            </Card>
          );
        })}
      </Card.Group>
    </>
  );
}

RequirementCards.propTypes = {
  profile: PropTypes.object.isRequired,
  types: PropTypes.instanceOf(Map).isRequired,
  counts: PropTypes.object.isRequired,
};
