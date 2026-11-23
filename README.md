# oarepo-pgd

Profile-guided deposition for [CESNET Invenio](https://nrp-cz.github.io/docs/) (OARepo) repositories. Prototype.

A deposition profile says which files a dataset should contain. Depositors select a profile, upload files and confirm what each file is. The repository counts the files against the profile and blocks publication until the requirements are met.

## Requirements

A CESNET Invenio repository on `oarepo-app` 8 (OARepo 14.2, InvenioRDM 14), generated from the standard templates.

## Use in a repository

1. Add the package:

   ```sh
   uv add git+https://github.com/sb-ncbr/oarepo-pgd --tag v0.2.0
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

   Profiles go in `models/<model>/config/profiles/*.yaml`, one profile per file:

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

   The full format is in `oarepo_pgd/configuration.schema.json`. A mistake in a YAML file stops the repository at startup with a message naming the file. So does a missing configuration: an enabled preset needs at least one profile, so deposits are never silently left unchecked. The preset defines the `deposition_profile` and `file_annotations` fields itself; a model that already defines either differently is refused.

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

   Without it the form says that the profiles are missing and keeps the publish button disabled.

5. Link the plugin's stylesheet in the repository's `templates/css.html`:

   ```jinja
   {{ webpack['oarepo_pgd_components.css'] }}
   ```

6. Run `./run.sh install` again, so the frontend is rebuilt with the plugin's components.

That is all for a repository with the standard deposit form. Labels, definitions and help texts in the YAML are shown as written.

## What the plugin adds

- Metadata fields `deposition_profile` and `file_annotations` on the model.
- A record-schema check: errors are reported on every draft save and block publication, including publication through publish requests and by API clients.
- The model's configuration in the deposit form's form config, as `deposition_profiles`.
- `GET /api/deposition-profiles?model=<model>` with the same configuration, for other software. `model` can be omitted while one model uses the plugin.
- Profile controls in the deposit form's files section, and a publish button that stays disabled until the files are known to meet the profile.
- English texts, ready for translation: form texts go through the plugin's i18next instance and server messages through gettext. Adding a language means adding two catalogues to the plugin: a `translations.json` in `theme/assets/semantic-ui/translations/oarepo_pgd/messages/<lang>/`, registered in that folder's `index.js`, and a `.po` file made from `translations/messages.pot`, compiled to `translations/<lang>/LC_MESSAGES/messages.mo`.

## Deposit form: standard and custom

**Standard form.** For a repository with the generated tabbed deposit form (`useWizardForm`), the plugin registers two overrides for each model's deposit pages: the tabbed form, whose files section it wraps, and the publish button. The files tab is renamed "Files and meanings" and shows an error badge when the server reports a profile problem. Nothing needs to be added to the host's JavaScript.

**Custom forms.** A host with its own deposit form switches the automatic overrides off in `invenio.cfg` and mounts the two components itself:

```python
OAREPO_PGD_UI_OVERRIDES = False
```

- *A custom tabbed form* that keeps a section with the key `files` and the `TabForm.PublishButton` slot wraps its sections and overrides the slot in its `forms/index.js`:

  ```js
  import { withProfiles, ProfilePublishButton } from "@js/oarepo_pgd";

  const sections = withProfiles(mySections);

  const componentOverrides = {
    [`${config.overridableIdPrefix}.TabForm.PublishButton`]: ProfilePublishButton,
  };
  ```

- *A form without tabs*, or without those two places, renders `ProfileFields` around its uploader and `ProfilePublishButton` in its action area:

  ```js
  import { ProfileFields, ProfilePublishButton } from "@js/oarepo_pgd";

  <ProfileFields record={record} uploader={<MyUploader />} />
  <ProfilePublishButton record={record} />
  ```

  Both must be inside the form's Formik, Redux and form-config context, as the standard sections are. Showing server errors for `metadata.deposition_profile` and `metadata.file_annotations` next to the files is then the form's own task.

The plugin's tests cover the rules, annotation reconciliation, the form-config component and the registration of the overrides; they do not render the form. The standard form has been checked in a browser on a generated repository; the custom routes have not.

## Tests

```sh
python -m pytest tests          # needs an OARepo environment, e.g. a host's .venv
node --test tests/*.test.mjs
```

`tests/cases/rules.json` holds the rule cases shared by the Python and JavaScript suites, with the expected English messages. A change to a rule or message has to pass both.
