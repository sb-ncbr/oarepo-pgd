# Deposit form

The plugin's controls in the deposit form let depositors select a profile, see its requirements and assign meanings to their files. The form and the server apply the same rules: the form shows problems while the depositor works, and the server checks every saved draft and refuses publication until the draft meets its profile.

## Standard form

For a repository with the generated tabbed deposit form (`useWizardForm`), the plugin puts its controls into the files section of each model's deposit pages. Nothing needs to be added to the repository's JavaScript.

- The files tab is renamed **Files and meanings**. It shows an error badge when the server reports a profile problem, and the form's error summary lists the messages under **File meanings**.
- The depositor selects a profile. When the model has only one profile and the draft has none, the form selects it the first time the controls are shown; a depositor who clears it keeps the cleared selection while the form is open.
- The requirement cards show, for each requirement, the matching files counted so far, marked red when a required minimum is not reached or a maximum is exceeded, and yellow when a recommended minimum is not reached.
- For each uploaded file, the depositor confirms or changes the suggested meanings and can add a description. See [Suggestions](configuration.md#suggestions).
- Only completed uploads are counted. Annotations of files deleted in the form are removed. Annotations of files the draft does not have yet are kept; they apply once a file of that name is uploaded, for example when a new version imports the previous version's files.
- A record with files switched off (metadata only) shows no profile controls and is not checked.

The controls use the classes of the repository's theme, so the plugin brings no stylesheet.

Without `DepositionProfilesComponent` in the model's UI resource config, the form says that the profiles are missing.

## Custom forms

The plugin's automatic override replaces `<prefix>.WizardForm.container` on the model's deposit pages and adds the controls to the section with the key `files`. It leaves a form without such a section unchanged.

Switch the override off in `invenio.cfg` when the repository's form places the controls itself in a section with the key `files`, or replaces `<prefix>.WizardForm.container` itself:

```python
OAREPO_PGD_UI_OVERRIDES = False
```

A form whose own section renders `ProfileFields`, in a section with another key or in a form without tabs, works with the override left on.

- *A custom tabbed form* that keeps a section with the key `files` wraps its sections in its `forms/index.js`:

  ```js
  import { withProfiles } from "@js/oarepo_pgd";

  const sections = withProfiles(mySections);
  ```

  The wrapped section gets the label **Files and meanings**, the controls around its uploader and the two profile fields, so the tab shows the server's profile errors.

- *Any other form* renders `ProfileFields` around its uploader:

  ```js
  import { ProfileFields } from "@js/oarepo_pgd";

  <ProfileFields record={record} uploader={<MyUploader />} />
  ```

  It must be inside the form's Formik, Redux and form-config context, as the standard sections are. Showing the server's errors for `metadata.pgd_deposition_profile` and `metadata.pgd_file_annotations` next to the files is then the form's own task.

The override's ids start with a prefix derived from the `application_id` of the model's UI resource config. When the deposit page uses another prefix, it stops with an error that names the value to pass to `pgd_preset`, or asks to switch the override off.

A frontend outside the repository's deposit form uses the API; see [API](api.md).

## Replacing parts of the controls

Four parts of the controls are overridable components, in the standard and in custom forms. Their ids start with the form's prefix: the model's `application_id` with a capital letter, followed by `.Form`, for example `Datasets.Form`.

| ID | Component | Props |
|---|---|---|
| `<prefix>.ProfileFields.ProfileSelector` | `ProfileSelector` | `profiles`, `value` (the selected profile's id or `""`), `onChange(id)` |
| `<prefix>.ProfileFields.RequirementCards` | `RequirementCards` | `profile`, `types` (semantic types by id, a `Map`), `counts` (file count by requirement id) |
| `<prefix>.ProfileFields.FileAssignments` | `FileAssignments` | `configuration`, `profile`, `types`, `keys` (the uploaded files), `annotations`, `errors`, `onAnnotationChange(key, changes)` |
| `<prefix>.ProfileFields.SemanticDefinitions` | `SemanticDefinitions` | `semanticTypes` |

A replacement receives the same props as the plugin's component. The plugin computes the counts and errors, and `onAnnotationChange` merges the changed fields, such as `description` or the full `semantic_types` list, into the file's annotation in the form. The plugin's components are exported from `@js/oarepo_pgd`, so a replacement can also wrap one. For example, a short list of requirements in place of the cards:

```js
// ui/datasets/semantic-ui/js/datasets/forms/MyRequirementCards.jsx
import React from "react";
import { List } from "semantic-ui-react";
import { countNotation } from "@js/oarepo_pgd";

export const MyRequirementCards = ({ profile, counts }) => (
  <List>
    {profile.requirements.map((requirement) => (
      <List.Item key={requirement.id}>
        {requirement.label}: {counts[requirement.id] ?? 0} / {countNotation(requirement)}
      </List.Item>
    ))}
  </List>
);
```

Register a replacement for both deposit pages, for example in the `ui_overrides` function of `ui/<model>/__init__.py`:

```python
from oarepo_ui.overrides import UIComponent, UIComponentOverride

cards = UIComponent("MyRequirementCards", "@js/datasets/forms/MyRequirementCards")
for page in ("deposit_create", "deposit_edit"):
    app.config["OAREPO_UI_OVERRIDES"].add(
        UIComponentOverride(f"datasets_ui.{page}", "Datasets.Form.ProfileFields.RequirementCards", cards)
    )
```

Then run `./run.sh install` to rebuild the frontend.

## Record page

The **File meanings** table shows the selected profile and, for each file the page lists, its semantic types and description. A reader who may not read the files sees no file list and no table. Include it in the model's record page template, as in step 5 of the [installation](../README.md#installation).

`DepositionProfilesComponent` puts the data in the page's `extra_context` as `pgd_file_meanings`. A repository that wants other markup puts its own `templates/oarepo_pgd/record_detail/file_meanings.html` in the repository, using the same data.

## Languages

The plugin's texts come in English and Czech: form texts through the plugin's i18next instance, server messages through gettext. Adding another language means adding two catalogues to the plugin: a `translations.json` in `theme/assets/semantic-ui/translations/oarepo_pgd/messages/<lang>/`, registered in that folder's `index.js`, and a `.po` file made from `translations/messages.pot`, compiled to `translations/<lang>/LC_MESSAGES/messages.mo`. The configuration's texts can be given in any language; see [Texts and languages](configuration.md#texts-and-languages).
