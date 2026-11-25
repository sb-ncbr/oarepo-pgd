import React from "react";
import PropTypes from "prop-types";
import { Button, Form, Message, Table } from "semantic-ui-react";
import { i18next } from "@translations/oarepo_pgd";
import { fileAlerts, messageText } from "./logic.mjs";

const t = (message, params) => i18next.t(message, params);
const sentence = (text) => text.charAt(0).toUpperCase() + text.slice(1);

/** One row per uploaded file to describe it and assign its meanings. */
export function FileAssignments({ configuration, profile, types, keys, annotations, errors, onAnnotationChange }) {
  const permitted = new Set(profile.semantic_types.map((type) => type.id));

  return (
    <>
      <h3 className="rel-mt-2">{t("File assignments")}</h3>
      <p>{t("Review the suggested meanings for each file and change them if needed.")}</p>
      {!keys.length ? <p>{t("No completed uploads yet.")}</p> : (
        <Table celled>
          <Table.Header>
            <Table.Row>
              <Table.HeaderCell>{t("File and description")}</Table.HeaderCell>
              <Table.HeaderCell>{t("Semantic types")}</Table.HeaderCell>
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {keys.map((key, index) => {
              const annotation = annotations.find((item) => item.file_key === key) ?? {};
              const assigned = annotation.semantic_types ?? [];
              const describe = assigned.some((id) => types.get(id)?.requires_description);
              const alerts = fileAlerts(errors, key);
              return (
                <Table.Row key={key}>
                  <Table.Cell className="text-break">
                    <strong>{key}</strong>
                    <Form.Input
                      // File names are not valid ids; the row number ties the label to its input.
                      id={`file-description-${index}`}
                      label={describe ? t("Description (required)") : t("Description (optional)")}
                      aria-label={t("{{file}} description", { file: key })}
                      value={annotation.description ?? ""}
                      onChange={(event) => onAnnotationChange(key, { description: event.target.value })}
                    />
                    {alerts.length > 0 && (
                      <Message negative size="small" role="alert">
                        <Message.List>
                          {alerts.map(({ id, error }) => (
                            <Message.Item key={id}>{sentence(messageText(error, t))}</Message.Item>
                          ))}
                        </Message.List>
                      </Message>
                    )}
                  </Table.Cell>
                  <Table.Cell>
                    <div role="group" aria-label={t("{{file}} semantic types", { file: key })}>
                      {configuration.semantic_types
                        .filter((type) => permitted.has(type.id) || assigned.includes(type.id))
                        .map((type) => (
                          // A toggle button reports its state through aria-pressed.
                          <Button key={type.id} type="button" size="small" compact toggle className="mb-5" title={type.definition}
                            active={assigned.includes(type.id)}
                            onClick={() => onAnnotationChange(key, {
                              semantic_types: assigned.includes(type.id)
                                ? assigned.filter((id) => id !== type.id)
                                : [...assigned, type.id],
                            })}>
                            {permitted.has(type.id) ? type.label : t("{{label}} (unsupported)", { label: type.label })}
                          </Button>
                        ))}
                      {assigned.filter((id) => !types.has(id)).map((id) => (
                        <Button key={id} type="button" size="small" compact basic negative className="mb-5"
                          onClick={() => onAnnotationChange(key, { semantic_types: assigned.filter((other) => other !== id) })}>
                          {t("Remove unknown type: {{type}}", { type: id })}
                        </Button>
                      ))}
                    </div>
                  </Table.Cell>
                </Table.Row>
              );
            })}
          </Table.Body>
        </Table>
      )}
    </>
  );
}

FileAssignments.propTypes = {
  configuration: PropTypes.object.isRequired,
  profile: PropTypes.object.isRequired,
  types: PropTypes.instanceOf(Map).isRequired,
  keys: PropTypes.arrayOf(PropTypes.string).isRequired,
  annotations: PropTypes.array.isRequired,
  errors: PropTypes.array.isRequired,
  onAnnotationChange: PropTypes.func.isRequired,
};
