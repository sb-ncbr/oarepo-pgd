# oarepo-pgd

Profile-guided deposition for [CESNET Invenio](https://nrp-cz.github.io/docs/) (OARepo) repositories.

A deposition profile says which files a dataset should contain. Depositors select a profile, upload files and confirm what each file is. The repository counts the files against the profile and blocks publication until the requirements are met.

## Requirements

A CESNET Invenio repository on `oarepo-app` 8 (OARepo 14.2, InvenioRDM 14), generated from the standard templates.

## Use in a repository

1. Add the package:

   ```sh
   uv add git+https://github.com/sb-ncbr/oarepo-pgd --tag v0.3.1
   ```

2. Enable it on a model, in `models/<model>/model.py`:

   ```python
   from oarepo_pgd import pgd_preset

   presets=[rdm_complete_preset, pgd_preset(__file__)],
   ```

3. Describe file types and profiles in YAML next to the model. Semantic types go in `models/<model>/config/semantic-types/*.yaml`, each file a list:

   ```yaml
   - id: interview-transcript
     label: Interview transcript
     definition: A written transcription of an interview session.
   ```

   Profiles go in `models/<model>/config/profiles/*.yaml`, one profile per file. Files ending in `.yml` are read too:

   ```yaml
   id: transcribed-interview
   revision: "1.0"
   dataset_category: Transcribed interview
   semantic_types:
     - id: interview-transcript
       filename_patterns: ["*transcript*.pdf", "interview.txt"]
       formats: [txt, pdf]
   requirements:
     - id: transcripts
       label: Transcripts
       level: required
       min_files: 1
       semantic_types: [interview-transcript]
       help: Provide a written transcription of the interview.
   ```

   A requirement's `level` says what a file count below `min_files` means:

   - `required`: an error. The form marks the requirement red and publication is blocked.
   - `recommended`: a notice. The form marks the requirement yellow and publication stays open. `min_files` must be at least 1.
   - `optional`: nothing. `min_files` must be 0.

   A count above `max_files` is an error at every level.

   The full format is defined by the schemas in `oarepo_pgd/config_schema.py`. A mistake in a YAML file, or a folder or file that cannot be read, stops the repository at startup with a message naming the file. So does a missing configuration directory or a configuration without profiles: an enabled preset needs at least one profile, so deposits are never silently left unchecked. The preset defines the `pgd_deposition_profile` and `pgd_file_annotations` fields itself. The `pgd_` prefix keeps them apart from fields of the model and of other packages; if the model or another package already defines either field, the repository stops at startup and names the field. A definition identical to the preset's own, including its search filters, is accepted, so applying the preset again changes nothing.

4. Give the deposit form the configuration: add the plugin's component to the `components` list of the model's UI resource config class, in `ui/<model>/__init__.py`, after the entries already there:

   ```python
   from oarepo_pgd.components import DepositionProfilesComponent


   class DatasetsUIResourceConfig(RDMRecordsUIResourceConfig):
       ...
       components = [
           *RDMRecordsUIResourceConfig.components,
           DepositionProfilesComponent,
       ]
   ```

   Without it the form says that the profiles are missing.

5. Show the file meanings on the record page: include the plugin's template in `ui/<model>/templates/semantic-ui/<model>/record_detail/main.html`, for example among the additional record details:

   ```jinja
   {%- block additional_record_details -%}
     {{ super() }}
     {% include "oarepo_pgd/record_detail/file_meanings.html" %}
   {%- endblock additional_record_details -%}
   ```

6. Run `./run.sh install` again, so the frontend is rebuilt with the plugin's components.

That is all for a repository with the standard deposit form.

Labels, definitions, profile names and help texts in the YAML are either a string, shown in every language, or a mapping of language codes to strings, shown in the reader's language with English as the fallback:

```yaml
- id: interview-transcript
  label: {en: Interview transcript, cs: Přepis rozhovoru}
  definition:
    en: A written transcription of an interview session.
    cs: Písemný přepis rozhovoru.
```

In the short form `{en: ..., cs: ...}`, quote a text that contains a comma, or write the mapping on separate lines as for `definition` above; otherwise YAML splits the text and the repository refuses to start, naming the file.

## What the plugin adds

- Metadata fields `pgd_deposition_profile` and `pgd_file_annotations` on the model. A user who may not read a record's files does not see its `pgd_file_annotations`, which name and describe those files; the selected profile stays visible. The search index holds the annotations only while the model's permission policy, including its workflow, lets a reader who is not logged in read the record's files, so search queries and the **File types** filter cannot reveal restricted files. When the policy cannot be checked, the annotations are left out of the index. A record with restricted files therefore shows no annotations in search results, also to users who may read its files; its record page and the record API show them to those users.
- Two search filters on the search page and in the search API: **Dataset category** (`metadata.pgd_deposition_profile.id`, the selected profile) and **File types** (`metadata.pgd_file_annotations.semantic_types`, the types assigned to the record's files). They show the labels from the YAML and count records, so a record with three recordings counts once under its type. **File types** counts only records whose files anyone may read. A semantic type with `search_filter: false` in its definition, such as a catch-all `other`, is left out of **File types**. A repository without facet groups shows them with all other filters; a repository with facet groups lists them in a group with `AddFacetGroup`, by these names.
- A record-schema check: errors are reported on every draft save and block publication, including publication through publish requests and by API clients.
- Annotations that follow the files. An annotation of a file the draft does not have is ignored by the check, so a client can save annotations before uploading the files, and a draft of a new version keeps the previous version's annotations until its files are imported. A published record keeps only the annotations of its own files.
- The model's configuration in the deposit form's form config, as `deposition_profiles`.
- `GET /api/deposition-profiles?model=<model>` with the same configuration, for other software, with texts in all their languages. `model` can be omitted while one model uses the plugin.
- Profile controls in the deposit form's files section. They use the classes of the repository's theme, so the plugin has no stylesheet.
- A **File meanings** table on the record page: the selected profile and, for each file the page lists, its semantic types and description. A reader who may not read the files sees no file list and no table. The component puts the data in the page's `extra_context` as `pgd_file_meanings`, so a repository that wants other markup puts its own `templates/oarepo_pgd/record_detail/file_meanings.html` in the repository, using the same data.
- English and Czech texts: form texts go through the plugin's i18next instance and server messages through gettext. Adding another language means adding two catalogues to the plugin: a `translations.json` in `theme/assets/semantic-ui/translations/oarepo_pgd/messages/<lang>/`, registered in that folder's `index.js`, and a `.po` file made from `translations/messages.pot`, compiled to `translations/<lang>/LC_MESSAGES/messages.mo`.

## Deposit form: standard and custom

**Standard form.** For a repository with the generated tabbed deposit form (`useWizardForm`), the plugin overrides the tabbed form of each model's deposit pages and wraps its files section. The files tab is renamed "Files and meanings" and shows an error badge when the server reports a profile problem; the form's error summary lists the messages under **File meanings**. Nothing needs to be added to the host's JavaScript.

**Custom forms.** A host with its own deposit form switches the automatic override off in `invenio.cfg` and mounts the profile controls itself:

```python
OAREPO_PGD_UI_OVERRIDES = False
```

- *A custom tabbed form* that keeps a section with the key `files` wraps its sections in its `forms/index.js`:

  ```js
  import { withProfiles } from "@js/oarepo_pgd";

  const sections = withProfiles(mySections);
  ```

- *A form without tabs*, or without a `files` section, renders `ProfileFields` around its uploader:

  ```js
  import { ProfileFields } from "@js/oarepo_pgd";

  <ProfileFields record={record} uploader={<MyUploader />} />
  ```

  It must be inside the form's Formik, Redux and form-config context, as the standard sections are. Showing server errors for `metadata.pgd_deposition_profile` and `metadata.pgd_file_annotations` next to the files is then the form's own task.

**Restyling parts of the controls.** Four parts of the profile controls are overridable components, in the standard and in custom forms. Their IDs start with the form's prefix: the model's application id with a capital letter, followed by `.Form`, for example `Datasets.Form`.

| ID | Component | Props |
|---|---|---|
| `<prefix>.ProfileFields.ProfileSelector` | `ProfileSelector` | `profiles`, `value` (the selected profile's id or `""`), `onChange(id)` |
| `<prefix>.ProfileFields.RequirementCards` | `RequirementCards` | `profile`, `types` (semantic types by id, a `Map`), `counts` (file count by requirement id) |
| `<prefix>.ProfileFields.FileAssignments` | `FileAssignments` | `configuration`, `profile`, `types`, `keys` (the uploaded files), `annotations`, `errors`, `onAnnotationChange(key, changes)` |
| `<prefix>.ProfileFields.SemanticDefinitions` | `SemanticDefinitions` | `semanticTypes` |

A replacement receives the same props as the plugin's component. The plugin computes the counts and errors, and `onAnnotationChange` merges the changed fields, such as `description` or the full `semantic_types` list, into the file's annotation in the form. The plugin's components are exported from `@js/oarepo_pgd`, so a replacement can also wrap one. Register a replacement for both deposit pages, for example in the `ui_overrides` function of `ui/<model>/__init__.py`:

```python
from oarepo_ui.overrides import UIComponent, UIComponentOverride

cards = UIComponent("MyRequirementCards", "@js/datasets/forms/MyRequirementCards")
for page in ("deposit_create", "deposit_edit"):
    app.config["OAREPO_UI_OVERRIDES"].add(
        UIComponentOverride(f"datasets_ui.{page}", "Datasets.Form.ProfileFields.RequirementCards", cards)
    )
```

## Tests

```sh
python -m pytest tests          # needs an OARepo environment, e.g. a host's .venv
node --test tests/*.test.mjs
```

`tests/cases/rules.json` holds the rule cases shared by the Python and JavaScript suites, with the expected English messages. A change to a rule or message has to pass both.
