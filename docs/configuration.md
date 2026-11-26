# Configuration

A model's semantic types and deposition profiles are YAML files next to the model, in `models/<model>/config/`:

- `semantic-types/` holds the semantic types: what a file can be, such as "Interview transcript". Each file is a list of types.
- `profiles/` holds the deposition profiles: which files a kind of dataset should contain. Each file is one profile.

Files ending in `.yaml` or `.yml` are read. A semantic type is defined once and can be used by several profiles. The configuration is read when the repository starts; see [Changing the configuration](#changing-the-configuration).

To keep the files elsewhere, name the directory: `pgd_preset(__file__, directory="deposition")` for a directory next to the model, or `pgd_preset("/path/to/configuration")` with the directory's path in place of `__file__`.

## Semantic types

```yaml
- id: interview-transcript
  label: Interview transcript
  definition: A written transcription of an interview session.
  uri: https://example.org/terms/interview-transcript
- id: interview-guide
  label: Interview guide
  definition: The questions or prompts used by the interviewer.
- id: other
  label: Other
  definition: A file that none of the other types describe.
  requires_description: true
  search_filter: false
```

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Identifier stored in the file annotations. Lowercase letters, digits, `-` and `_`, starting with a letter or digit. |
| `label` | yes | Name shown to depositors and readers. A [text](#texts-and-languages). |
| `definition` | yes | What the type means, shown with the type in the form. A text. |
| `uri` | no | An `http` or `https` address of the same term in a vocabulary. |
| `requires_description` | no | `true`: a file with this type needs a description. Useful for a catch-all type. Default `false`. |
| `search_filter` | no | `false`: the type is left out of the **File types** search filter. Default `true`. |

## Profiles

```yaml
id: transcribed-interview
revision: "1.0"
dataset_category: Transcribed interview
semantic_types:
  - id: interview-transcript
    filename_patterns: ["interview.txt", "*transcript*.pdf"]
    formats: [txt, pdf]
  - id: interview-guide
    filename_patterns: ["*guide*.pdf"]
requirements:
  - id: transcripts
    label: Transcripts
    level: required
    min_files: 1
    semantic_types: [interview-transcript]
    help: Provide a written transcription of the interview.
  - id: guides
    label: Interview guides
    level: recommended
    min_files: 1
    semantic_types: [interview-guide]
    help: Add the questions or prompts used by the interviewer.
```

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Identifier stored with the draft or record. Same form as a semantic type's `id`. |
| `revision` | yes | Version of the profile, stored with the draft or record. Quote it, for example `"1.0"`, so YAML keeps it a text. |
| `dataset_category` | yes | Name of the profile in the selector, the **Dataset category** search filter and the record page. A text. |
| `semantic_types` | yes | The semantic types files may have under this profile, at least one. |
| `requirements` | yes | The file requirements; may be empty. |

Each entry of `semantic_types` names a defined type and can add:

- `filename_patterns`: names that suggest the type for a newly uploaded file. See [Suggestions](#suggestions).
- `formats`: the file extensions the type accepts, such as `[txt, pdf]`. A file with this type and another extension is an error. Without `formats`, any extension is accepted.

## Requirements

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Identifier, unique within the profile. |
| `label` | yes | Name shown on the requirement card and in messages. A text. |
| `level` | yes | `required`, `recommended` or `optional`; see below. |
| `min_files` | yes | The number of matching files asked for. |
| `max_files` | no | The largest number of matching files allowed, at least 1. |
| `semantic_types` | yes | The types that count toward the requirement, at least one, each permitted by the profile. |
| `help` | no | Advice for the depositor, shown on the card and added to the message when too few files match. A text. |

The level says what a count below `min_files` means:

| Level | Below `min_files` | `min_files` must be |
|---|---|---|
| `required` | An error: the form marks the requirement red and publication is refused. | 0 or more |
| `recommended` | A notice: the form marks the requirement yellow and publication stays open. | at least 1 |
| `optional` | Nothing. | 0 |

A count above `max_files` is an error at every level.

A file counts toward a requirement when it has any of the requirement's types. Each file counts once per requirement, also when it has several of its types; a file with types of two requirements counts toward both. Only files whose upload has completed are counted.

## Suggestions

For each uploaded file without an annotation, the deposit form suggests a type from the selected profile's `filename_patterns`, also for files already on the draft when the form opens. The depositor can change or remove the suggestion before saving. Suggestions are made only in the form; the server stores what the form saves.

- A pattern matches the whole file name, ignoring case. `*` matches any characters; every other character matches itself.
- When several patterns match, the most specific wins: the one with the most characters besides `*`.
- When equally specific patterns of different types match, no type is suggested and the depositor chooses.

For example, with `*.pdf` for one type and `*guide*.pdf` for another, `interview-guide.pdf` gets the second type.

## Texts and languages

Labels, definitions, profile names and help texts are either one text, shown in every language, or a mapping of language codes to texts, shown in the reader's language. When the reader's language is missing, English is shown, and without English the first text given:

```yaml
- id: interview-transcript
  label: {en: Interview transcript, cs: Přepis rozhovoru}
  definition:
    en: A written transcription of an interview session.
    cs: Písemný přepis rozhovoru.
```

Language codes have two or three lowercase letters. In the short form `{en: ..., cs: ...}`, quote a text that contains a comma, or write the mapping on separate lines as for `definition` above; otherwise YAML splits the text and the repository refuses to start, naming the file.

## Checks at startup

The repository refuses to start with a configuration that has a mistake, and names the file and the field, for example:

```text
profiles/gromacs.yaml: requirement 'topology' is recommended, so min_files must be at least 1
```

It checks:

- that each file is valid YAML, without a key repeated in one mapping. A key may still override a value merged with `<<`.
- that each file can be read and is not empty;
- the fields and values described above;
- that semantic type, profile and requirement identifiers are not repeated;
- that a profile permits only defined types, and its requirements only permitted types;
- the `min_files` rule of each level, and that `max_files` is not below `min_files`;
- that requirements over the same types can be met together: a required `min_files` above another such requirement's `max_files` would refuse every deposit;
- that the model has a configuration directory and at least one profile, so deposits are never left unchecked.

The preset also refuses to start when the model or another package already defines `pgd_deposition_profile` or `pgd_file_annotations`, and names the field. A definition identical to the preset's, including its search filters, is accepted. The preset goes into a model's `presets` once.

## Changing the configuration

The configuration is read when the repository starts. After a change, restart the web and worker processes. The search filters' labels follow the configuration; the search index needs no rebuild.

Drafts and records store the profile's `id` and `revision` and the types' `id`s:

- Change a profile's `revision` when its requirements or permitted types change. A draft that selected an earlier revision is asked to select the profile again and review the file meanings before it can be published. Published records keep the revision they were published with.
- Keep the `id`s of profiles and types that records use. A draft whose profile is no longer configured is asked to select a profile. On the record page, a type that is no longer configured is shown by its `id`.
