# FileSteward

> **Review first. Organize safely. Delete nothing silently.**

FileSteward is a human-in-the-loop file triage project for Downloads and other user-selected folders. It is intended to inventory files, classify them by subject, produce a review queue, and apply only actions that a person has explicitly approved.

## Status

**Design-stage / pre-alpha.**

The repository currently defines the product and safety contract. The scanner, review queue, executor, WinDirStat adapter, duplicate analysis, and optional AI enrichment are planned work unless a later release and its validation evidence state otherwise.

## Why FileSteward exists

Downloads folders mix temporary installers, important records, project artifacts, archives, duplicates, incomplete downloads, and files whose purpose is unclear. A simple keyword sorter can move the wrong item, while an automatic cleaner can destroy information before its value is understood.

FileSteward separates three decisions that should not be conflated:

1. **Inventory:** What is present, where is it, and how much space does it use?
2. **Classification:** What subject or purpose does the file appear to belong to?
3. **Action:** Should it stay, move, be renamed, be archived, be inspected, or enter a cleanup review?

A classification is evidence. It is not permission to modify a file.

## Planned workflow

```text
Native scan or WinDirStat export
              ↓
     Normalized inventory
              ↓
  Deterministic rule evidence
              ↓
 Optional AI recommendation
              ↓
       Human review queue
              ↓
       Dry-run validation
              ↓
 Approved move or quarantine
              ↓
      Audit and restore record
```

## Safety contract

FileSteward is designed around the following non-negotiable rules:

- Scanning does not modify source files.
- Recommendations do not directly become filesystem actions.
- Only explicitly approved queue rows are eligible for execution.
- Permanent deletion is not part of the initial MVP.
- Cleanup candidates go to a quarantine location first.
- Destination collisions are never silently overwritten.
- Source paths must remain inside the user-approved root.
- Every applied action produces an audit record.
- Missing, changed, or ambiguous files are reported rather than guessed away.
- Private file contents are not sent to an external model by default.

## Subject and action are separate

A **subject** answers, “What is this file about?”

Planned subjects include:

- Work
- Projects
- Finance
- Personal
- School
- Entertainment
- Software
- Photos
- Records
- Other
- Unknown

An **action** answers, “What should happen to this file?”

Planned actions include:

- Keep in place
- Move to a subject folder
- Rename and move
- Archive
- Inspect contents
- Review as a possible duplicate
- Review as a cleanup candidate
- Quarantine
- Protect from automation
- Take no action

A Finance file may stay where it is. A Software file may be valuable. A large or old file is not automatically disposable.

## MVP boundary

The first executable milestone is intended to provide:

- A top-level scan of a user-selected folder
- A normalized inventory
- Deterministic subject and file-kind evidence
- A CSV review queue
- Human-editable final subject, action, status, destination, and notes fields
- Dry-run execution by default
- Approved moves into organized subject folders
- Approved cleanup moves into quarantine
- Collision-safe destinations
- A JSON Lines action log
- Synthetic fixtures and tests for the safety contract

The initial milestone will not:

- Permanently delete files
- Recursively reorganize an entire drive by default
- Open every document automatically
- Upload file contents to an external AI service without explicit approval
- Treat similarly named files as proven duplicates
- Automatically unpack archives
- Infer that an installer is safe to remove solely from age
- Modify Windows or application-managed system folders

## Review queue contract

A review queue should preserve both machine evidence and the final human decision. The planned schema includes:

| Field | Purpose |
|---|---|
| `item_id` | Stable identifier for the queue item |
| `source_path` | Current absolute path |
| `filename` | Current filename |
| `extension` | File extension |
| `size_bytes` | Logical size |
| `modified_at` | Last modified timestamp |
| `age_days` | Age at scan time |
| `file_kind` | Document, archive, installer, image, partial download, and so on |
| `rule_subject` | Subject suggested by deterministic rules |
| `rule_confidence` | Confidence in the deterministic classification |
| `recommended_action` | Proposed action |
| `reason` | Plain-language evidence for the recommendation |
| `ai_subject` | Optional AI classification |
| `ai_action` | Optional AI action recommendation |
| `ai_confidence` | Optional AI confidence |
| `ai_reason` | Optional AI explanation |
| `final_subject` | Human-approved subject |
| `final_action` | Human-approved action |
| `status` | Unreviewed, approved, rejected, deferred, or completed |
| `destination` | Approved destination path |
| `notes` | Human notes |

Deterministic and AI recommendations should remain visible independently. AI output must not overwrite the original evidence.

## Evidence hierarchy

Recommendations should prefer stronger evidence over weaker inference:

1. Exact duplicate hash
2. Protected-location or protected-file rule
3. Explicit user rule
4. Existing organized destination
5. File metadata and extension
6. Filename keywords
7. Parent-folder and neighboring-file context
8. Explicitly authorized content inspection
9. AI inference
10. File age by itself

Age and size are prioritization signals, not deletion proof.

## WinDirStat integration

WinDirStat is useful as an upstream disk-usage and inventory evidence source. FileSteward is intended to normalize WinDirStat exports into the same review queue used by its native scanner.

WinDirStat does not decide whether a file is meaningful or disposable. FileSteward adds the subject model, cleanup reasoning, human approval gate, quarantine behavior, and audit trail.

The native scanner remains important so the project does not depend on one graphical application or export format.

## Privacy modes

The planned inspection model has three levels:

### Metadata only — default

The classifier may use filename, extension, size, dates, and folder context. File contents are not read.

### Local content inspection

An explicitly enabled local process may extract limited metadata or text, such as document properties, archive member names, media duration, or a small text sample.

### Explicit external inspection

Selected metadata or extracted content may be sent to a configured external model only after the user enables that path and approves its scope.

## Planned command-line shape

The command names below describe the intended interface; they are not install instructions until the CLI is implemented and validated.

```powershell
filesteward scan "$env:USERPROFILE\Downloads" --queue .\var\downloads-review.csv
filesteward validate .\var\downloads-review.csv
filesteward apply .\var\downloads-review.csv
filesteward apply .\var\downloads-review.csv --execute
```

`apply` should remain a dry run unless the explicit execution flag is present.

## Planned repository layout

```text
FileSteward/
├── src/filesteward/       # Package implementation
├── tests/                 # Automated tests
├── tests/fixtures/        # Synthetic, non-private fixtures
├── examples/              # Sanitized examples safe to commit
├── schemas/               # Queue and report contracts
├── docs/                  # Architecture and operational decisions
├── scripts/               # Repository and validation helpers
└── var/                   # Ignored local runtime output
```

Real inventories, filenames, hashes, extracted metadata, queue decisions, quarantine contents, and action logs belong in ignored runtime locations. Sanitized examples and synthetic test fixtures belong in version control.

## Roadmap

### Phase 1 — Review queue foundation

- Native top-level scanner
- Deterministic classification
- CSV queue
- Dry-run and approved-action executor
- Quarantine and audit log
- Safety-contract tests

### Phase 2 — Better evidence

- Exact duplicate hashing
- Archive member listing
- Extracted-folder detection
- Installer review evidence
- Suggested renames
- Restore manifest and verified restoration

### Phase 3 — Optional AI enrichment

- Metadata-only structured classification
- Local extraction adapters
- Confidence thresholds
- Learning from approved decisions without bypassing review
- Explicit privacy and provider controls

### Phase 4 — Local review interface

- Filterable queue
- Open file and reveal in Explorer
- Approve, reject, defer, rename, and choose destination
- Quarantine and restore controls
- Estimated recoverable-space reporting

The interface should call the same scanner, schemas, validators, and executor as the CLI rather than introducing a second decision system.

## Development principles

- Evidence before confidence
- Dry run before mutation
- Explicit paths before broad filesystem access
- Structured outputs before prose-only logs
- Synthetic fixtures before personal data
- Reversible actions before destructive actions
- One shared contract for CLI, dashboard, and adapters
- Tests must prove behavior; documentation must not claim a higher proof level

## License

FileSteward is licensed under the [MIT License](LICENSE).
