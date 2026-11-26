# API

This page is for frontends and other software that deposit through the repository's REST API, without the repository's deposit form. They use the repository's usual record, draft, file and request endpoints, two metadata fields the plugin adds, and two endpoints of the plugin: the configuration and the check of a saved draft.

The repository applies the rules itself: every draft save reports profile problems, and publication is refused until the draft meets its profile. A client shows these results and helps the depositor fix them.

The examples on this page use the Transcribed interview profile from [Configuration](configuration.md), with Czech names added.

## The fields

The plugin adds two fields to the model's metadata:

```json
{
  "metadata": {
    "pgd_deposition_profile": {"id": "transcribed-interview", "revision": "1.0"},
    "pgd_file_annotations": [
      {"file_key": "interview.txt", "semantic_types": ["interview-transcript"]},
      {"file_key": "questions-guide.pdf", "semantic_types": ["interview-guide"], "description": "Questions for all sessions."}
    ]
  }
}
```

- `pgd_deposition_profile` names the selected profile with its `revision`, both from the configuration. The client sets it, also when the model has only one profile.
- `pgd_file_annotations` has one entry per file: the file's key in the draft, its semantic types and an optional description. A file can have several types.

Annotations follow the files:

- An annotation of a file the draft does not have is kept and ignored by the check, so a client can save annotations before uploading the files. It applies once a file of that name is there.
- Only files whose upload has completed are counted.
- A draft of a new version keeps the previous version's annotations until its files are imported.
- A published record keeps only the annotations of its own files.
- A record with files switched off (`"files": {"enabled": false}`) is not checked.

## Configuration

`GET /api/deposition-profiles?model=<model>` returns the model's semantic types and profiles, as described in [Configuration](configuration.md), with texts in all their languages. `model` can be omitted while one model uses the plugin. It needs no login.

```json
{
  "semantic_types": [
    {"id": "interview-transcript", "label": {"en": "Interview transcript", "cs": "Přepis rozhovoru"},
     "definition": "A written transcription of an interview session.",
     "uri": "https://example.org/terms/interview-transcript"},
    {"id": "interview-guide", "label": {"en": "Interview guide", "cs": "Scénář rozhovoru"},
     "definition": "The questions or prompts used by the interviewer."},
    {"id": "other", "label": "Other", "definition": "A file that none of the other types describe.",
     "requires_description": true, "search_filter": false}
  ],
  "profiles": [
    {
      "id": "transcribed-interview",
      "revision": "1.0",
      "dataset_category": {"en": "Transcribed interview", "cs": "Přepsaný rozhovor"},
      "semantic_types": [
        {"id": "interview-transcript", "filename_patterns": ["interview.txt", "*transcript*.pdf"], "formats": ["txt", "pdf"]},
        {"id": "interview-guide", "filename_patterns": ["*guide*.pdf"]}
      ],
      "requirements": [
        {"id": "transcripts", "label": "Transcripts", "level": "required", "min_files": 1,
         "semantic_types": ["interview-transcript"], "help": "Provide a written transcription of the interview."},
        {"id": "guides", "label": "Interview guides", "level": "recommended", "min_files": 1,
         "semantic_types": ["interview-guide"], "help": "Add the questions or prompts used by the interviewer."}
      ]
    }
  ]
}
```

A text is either one string or a mapping of language codes to strings; show the reader's language, then English, then the first text given. A field with its default value is left out, for example `search_filter` while it is `true`; the defaults are in [Configuration](configuration.md). An unknown model returns `404`.

## Checking a draft

`GET /api/deposition-profiles/check?model=<model>&draft=<id>` returns the check of a saved draft, as publication would run it, with the count and state of each requirement. `model` can be omitted while one model uses the plugin.

For example, a draft with the uploaded files `interview.txt` and `notes.txt` and these annotations, where the depositor marked the transcript as a guide and has not described `notes.txt` yet:

```json
{
  "metadata": {
    "pgd_deposition_profile": {"id": "transcribed-interview", "revision": "1.0"},
    "pgd_file_annotations": [
      {"file_key": "interview.txt", "semantic_types": ["interview-guide"]}
    ]
  }
}
```

gets this check:

```json
{
  "model": "datasets",
  "draft": "kgegj-9at32",
  "files_enabled": true,
  "file_keys": ["interview.txt", "notes.txt"],
  "errors": [
    {"code": "meaning_missing", "file_key": "notes.txt", "requirement": null,
     "message": "select at least one file meaning."},
    {"code": "too_few_files", "file_key": null, "requirement": "transcripts",
     "message": "Transcripts: 0 of at least 1 file. Provide a written transcription of the interview."}
  ],
  "counts": {"transcripts": 0, "guides": 1},
  "states": {"transcripts": "unmet", "guides": "met"}
}
```

- `file_keys` are the draft's completed uploads, the files the check counts.
- `errors` block publication. Each has a stable `code`, the `file_key` or `requirement` it is about (or `null`), and a `message` in the request's language.
- `counts` and `states` are keyed by requirement id. A state is `met`, `unmet` (publication is refused) or `advised` (a recommended minimum is not reached; publication stays open). They are empty while the draft has no known profile or has files switched off.

| Code | About | Meaning |
|---|---|---|
| `profile_missing` | the draft | No profile is selected, or the selected one is not configured. |
| `profile_changed` | the draft | The selected revision is not the current one; select the profile again and review the meanings. |
| `annotation_repeated` | a file | The file has more than one annotation. |
| `meaning_missing` | a file | The file has no semantic type. |
| `meaning_repeated` | a file | The file has the same type twice. |
| `meaning_not_in_profile` | a file | The file has a type the profile does not permit. |
| `format_not_accepted` | a file | The file's extension is not among the type's `formats`. |
| `description_missing` | a file | The file has a type with `requires_description` and no description. |
| `too_few_files` | a requirement | Fewer matching files than a required `min_files`. |
| `too_many_files` | a requirement | More matching files than `max_files`. |

The check is of the draft as last saved. The caller needs permission to read the draft. For a draft with files, the caller also needs the permissions under which the draft API shows the files and their meanings: listing the files and reading the file annotations. A draft with files switched off returns `200` with an empty check to anyone who may read it. Without these permissions the check returns `403`; an unknown draft returns `404` and a deleted one `410`. An id redirected to another draft of the same model returns `301` with the check of its destination in `Location`; a redirect to an id of another kind returns `404`. Errors have the repository's usual form, `{"status": 403, "message": "Permission denied."}`.

## Saving and publishing

A draft save (`POST /api/<model>` or `PUT /api/<model>/<id>/draft`) returns `200` or `201` and keeps the draft also when it does not meet its profile. The problems come in the response's `errors`, under the field `metadata.pgd_file_annotations`, each message prefixed with its file key:

```json
{
  "errors": [
    {"field": "metadata.pgd_file_annotations",
     "messages": ["notes.txt: select at least one file meaning.",
                  "Transcripts: 0 of at least 1 file. Provide a written transcription of the interview."]}
  ]
}
```

The same messages, codes and counts come from the check endpoint, which a client can call after each save.

Publication is refused while errors remain. What the client sees depends on the repository's workflow:

- **Direct publication** (`POST /api/<model>/<id>/draft/actions/publish`): `400` with the same `errors`.
- **Publish request**, as in a repository generated from the standard templates: creating the request on a draft with errors returns `400` with the same `errors` and the message "A validation error occurred.". The draft lists `publish_draft` among its applicable requests also when it has errors, so check the draft before offering publication.
- **Accepting a request** after its draft was changed and no longer meets its profile returns `400` "Error for action 'accept': Could not execute the action", without the profile errors, and the request stays submitted. Check the draft before accepting, and accept again once it is fixed.

## Suggestions and checks in the client

The repository's deposit form suggests meanings from the profile's `filename_patterns` and checks the deposit while the depositor works, before saving. A client that does the same follows the rules in [Suggestions](configuration.md#suggestions) and the requirement rules in [Configuration](configuration.md#requirements). The form's implementation, `oarepo_pgd/theme/assets/semantic-ui/js/oarepo_pgd/logic.mjs`, has no framework dependency: `suggestType` makes the suggestions and `checkDeposit` returns the same codes, counts and states as the server. `tests/cases/rules.json` holds the cases both implementations are tested against. The server's check stays authoritative.

## Languages

Messages and the configuration's texts in check and save responses follow the request's language, from `Accept-Language` or `?ln=<code>`, when the repository offers that language. The configuration endpoint returns all languages.

## Visibility

The annotations name and describe a record's files, so they follow the files' access:

- A user who may not read a record's files does not see its `pgd_file_annotations` in the record or draft API, and gets `403` from the check of a draft with files; the selected profile stays visible.
- The search index holds the annotations only while a reader who is not logged in may read the record's files, so search queries and the **File types** filter cannot reveal restricted files. A record with restricted files therefore shows no annotations in search results, also to users who may read its files.
- The search responses carry two filters: **Dataset category** under `metadata.pgd_deposition_profile.id` and **File types** under `metadata.pgd_file_annotations.semantic_types`, with labels from the configuration. They count records, so a record with three recordings counts once under its type.

## Browser clients on another origin

A frontend served from another origin calls the API from the browser, which needs CORS. Invenio does not send CORS headers by default (`REST_ENABLE_CORS` is `False`); the repository enables and configures them in `invenio.cfg`. This applies to the whole API and is the repository's setting.
