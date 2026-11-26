# oarepo-pgd

Profile-guided deposition for [CESNET Invenio](https://nrp-cz.github.io/docs/) (OARepo) repositories.

A deposition profile says which files a dataset should contain. Depositors select a profile, upload files and confirm what each file is. The repository counts the files against the profile and blocks publication until the requirements are met.

## Requirements

A CESNET Invenio repository on `oarepo-app` 8 (OARepo 14.2, InvenioRDM 14), generated from the standard templates.

## Installation

1. Add the package to the `dependencies` of the `[project]` table in the repository's `pyproject.toml`, and its source:

   ```toml
   [project]
   dependencies = [
       # the repository's dependencies stay as they are
       "oarepo-pgd",
   ]

   [tool.uv.sources]
   oarepo-pgd = { git = "https://github.com/sb-ncbr/oarepo-pgd", tag = "v0.4.1" }
   ```

   The repository's `./run.sh` installs its packages from the CESNET package index, so add dependencies in `pyproject.toml` as the [NRP documentation](https://nrp-cz.github.io/docs/installation/run_script) does. A plain `uv add` does not use that index and fails to resolve the repository's other packages. Step 6 installs the package and updates `uv.lock`.

   To work on the plugin itself, add a local checkout instead. The repository runner adds it in editable mode and reinstalls the repository:

   ```sh
   ./run.sh local add ../oarepo-pgd
   ```

2. Enable it on a model: in `models/<model>/model.py`, append `pgd_preset(__file__)` to the model's existing `presets` list and keep the presets already there:

   ```python
   from oarepo_pgd import pgd_preset

   presets=[
       ...,  # the presets the model already has
       pgd_preset(__file__),
   ],
   ```

   The plugin adds its controls to the deposit form under ids built from the `application_id` of the model's UI resource config, in `ui/<model>/__init__.py`. The repository templates set it to the model name, which the preset assumes. If it differs, pass it: `pgd_preset(__file__, application_id="Samples")`. Otherwise the deposit page stops with an error that names the value to pass.

3. Describe the file types and profiles in YAML in `models/<model>/config/`: semantic types in `semantic-types/*.yaml`, one profile per file in `profiles/*.yaml`. For example:

   ```yaml
   # models/datasets/config/semantic-types/interviews.yaml
   - id: interview-transcript
     label: Interview transcript
     definition: A written transcription of an interview session.
   ```

   ```yaml
   # models/datasets/config/profiles/transcribed-interview.yaml
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

   The repository needs at least one profile to start. [Configuration](docs/configuration.md) describes every field, the requirement levels and the checks made at startup.

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

6. Run `./run.sh install`. It installs the package and rebuilds the frontend with the plugin's components.

   If the repository's services are already set up, its search index also needs the plugin's two metadata fields; until it has them, saving a draft with a profile fails. `./run.sh index rebuild` deletes the search indices, creates them again and queues every record for indexing. Search results are missing or incomplete until the workers have indexed all records, so plan the rebuild for a quiet time. Restart the web and worker processes first, so they run the installed plugin, and keep the workers running until the indexing has finished:

   ```sh
   ./run.sh index rebuild
   ```

That is all for a repository with the standard deposit form. A new repository then continues with `./run.sh services setup` as usual.

## What the plugin adds

- **Metadata fields** `pgd_deposition_profile` (the selected profile) and `pgd_file_annotations` (the semantic types and description of each file) on the model.
- **Deposit form:** in the standard tabbed form, the files tab becomes "Files and meanings" with a profile selector, requirement cards and the file assignments. See [Deposit form](docs/deposit-form.md) for custom forms and for replacing parts of the controls.
- **Checks:** every draft save reports profile problems, and publication is refused until the draft meets its profile, also through publish requests and for API clients.
- **Search filters:** **Dataset category** and **File types** on the search page and in the search API.
- **Record page:** a **File meanings** table with the selected profile and each file's meanings.
- **API:** the configuration at `GET /api/deposition-profiles` and the check of a saved draft at `GET /api/deposition-profiles/check`. See [API](docs/api.md) for frontends and other software.
- **Languages:** English and Czech for the plugin's own texts; the configuration's texts can be given in any language.

## Documentation

- [Configuration](docs/configuration.md): semantic types, profiles and requirements in YAML.
- [Deposit form](docs/deposit-form.md): the standard form, custom forms, replacing parts of the controls and the record page.
- [API](docs/api.md): the fields, the configuration and check endpoints, and what drafts and publication report, for independent frontends and other software.

## Tests

```sh
python -m pytest tests          # needs an OARepo environment, e.g. a repository's .venv
node --test tests/*.test.mjs
```

`tests/cases/rules.json` holds the rule cases shared by the Python and JavaScript suites, with the expected English messages, codes, counts and requirement states. A change to a rule or message has to pass both.
