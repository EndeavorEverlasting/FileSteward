# Local asset lifecycle — classification without false disposal

## Problem and decision

FileSteward already classifies repositories, installed apps, regenerable caches
and their dependency edges. Arbitrary local user paths have no comparable
lifecycle model. "Not Git", "not an installed app", "not a teaching workspace",
and "not recently modified" are negative observations, never evidence of
disposability. "Local" means storage location, not an action, owner or age class.

**Canonical owner:** src/filesteward/ownership/local.py (pure read-only
evidence projection). See harness/contracts/local-asset-lifecycle.v1.json.
This does not change the native owner adapters, deletion executor, review
scenes or scan contracts until the next integration gate is proven.

## Orthogonal dimensions

| Dimension | Examples | Authority |
|---|---|---|
| Identity | personal record, project, learning, reference, generated, other, unclassified | attributed metadata or declared meaning |
| Ownership | verified local/user, other owner, conflicting, unresolved | read-only adapter coverage + traceable evidence |
| Lifecycle | active, stable, dormant, legacy candidate, unresolved | current use/uniqueness/dependencies + explicit preferences |
| Disposition | PROTECTED, KEEP_PROVEN, HUMAN_REVIEW, UNKNOWN | existing FileSteward safety model |
| Review route | keep, resolve attribution/dependencies/recovery, review retention/archive/removal | deterministic rules |
| Authorization | UNAPPROVED, APPROVED_FOR_ACTION, APPLIED, VERIFIED | existing distinct exact artifact + preflight + executor |

Deletion target != mutation approval. "Legacy candidate" means **review for
possible archiving** after proof of recovery and nondependency; it is not a
deletion target. "Review removal" is not RECLAIM_PROVEN. If a user explicitly
declares an inactive folder but the sole unique copy is unbacked, retain as
PROTECTED. The independent signed exact-manifest path remains authoritative.

## Agent and operator path

1. Scope an exact user-authorized root. Do not scan real user storage merely
   because an agent was asked to discuss lifecycle classifications.
2. Invoke registered safe app, repository/worktree, learning-workspace,
   dependency, user-data and local-asset adapters. Record each provider's
   attempt, completeness, observed provenance, and unresolved questions.
   Current FileSteward native adapters are incomplete, so do not assert
   comprehensive coverage without evidence.
3. Encode a LOCAL_USER asset assessment *only after* current technical
   attribution is proven. Any collision with active app/repo/structural
   protection overrides general local interpretation. If no owner is
   identifiable, retain UNRESOLVED/UNKNOWN and route further attribution.
4. Record the operator's intent separately: KEEP, DORMANT, ARCHIVE_REVIEW,
   LEGACY_REVIEW, REMOVE_REVIEW, or UNDECLARED. Do not infer intent from file
   ages, inactivity, path depth or absence from Git/Entire.
5. Run the deterministic evaluator on adapter-authored JSON in ignored private
   runtime (no scan, source writes or content reads):
   
   python -m filesteward.ownership.local --example
   
   python -m filesteward.ownership.local --evidence-file var/runs/<run-id>/local-asset-evidence.json

   The first prints only a synthetic example; the second prints a JSON
   assessment with lifecycle, disposition, route, evidence revision, missing
   facts, and false mutation_authorized.
6. Route technical unknowns back into read-only attribution/proof, not to a
   person as a guess-the-technical-facts puzzle. Resolve operator-only value,
   preference, and bounded mutation authorization with separate gates.
7. Before any future action, refresh protective evidence, revalidate exact
   item identities/dependencies and invoke only the existing approved
   exact-manifest deletion lifecycle. Ordinary local classifier output is
   never an input substitute for reclaim proof.

## Deterministic outcomes

- Policy-protected, active-use, unbacked unique, conflicting or other-owner:
  retain PROTECTED.
- Operator-declared KEEP: KEEP_PROVEN; does not rely on complete adapters.
- Unattributed/incomplete coverage: UNKNOWN; resolve current attribution.
- Explicit dormant retention with complete negative active/dependency signals:
  DORMANT + KEEP_PROVEN.
- Local, complete, inactive and no unresolved dependents, but no retire intent:
  STABLE + HUMAN_REVIEW; review retention.
- Explicit LEGACY_REVIEW with complete proof (owner, inactivity, no unique
  unbacked work, no dependency, recoverable): LEGACY_CANDIDATE + HUMAN_REVIEW.
- Explicit REMOVE_REVIEW with the same technical proof:
  STABLE + REVIEW_REMOVAL + HUMAN_REVIEW; never RECLAIM_PROVEN or approval.
- Insufficient recovery/uniqueness/dependency proof: do not promote to legacy
  or removal candidate, present the exact missing fact instead.

These classes are not exhaustive forever; version the contract before
changing semantics. Known lower-trust adapter output may be used for
hypothesis generation, not for proven recovery/owner completeness.

## P97 prior art (observed source, 2026-10-24)

| Reference | Evidence | Pattern | Disposition |
|---|---|---|---|
| tfeldmann/organize (MIT), main tree a736516555d0daeb83a604448fbdf5379f42f2ef | organize/cli.py (sim/run), organize/rule.py (filter/action pipeline) | Separate selection, simulation and effects; not lifecycle authority | ADAPT |
| qarmin/czkawka (licenses per subcomponent; verify exact reuse), master tree eb8b91dbb4d25dff416202674ee0de84ee4b5e5c | czkawka_cli/src/commands.rs, czkawka_core/src/tools/duplicate/tests.rs | Explicit exclusions, references and separate deletion strategies | ADAPT |
| FileSteward existing graph/disposition stack, main@c3abf4984474b16a957f4148cf835880bfd7f93a | ownership/{graph,reducer,actions,current}.py; classify/rules.py; deletion/preflight.py | Multi-owner safety, UNKNOWN, HUMAN_REVIEW, exact separate mutation authorization | ALREADY_SOLVED_INTERNALLY |

Reference code was inspected as read-only evidence. No code was copied,
installed or attributed as having completed FileSteward's specific lifecycle
contract. REJECT deriving deletion eligibility from duplicates, location,
timestamps or existence/absence of an owning app/repo.

## Acceptance, placement and parent gate

Host for repo/provider writes: CURRENT_CHAT_RUNTIME through GitHub connector.
For actual workstation observations: LOCAL_AGENT_RUNTIME on an explicitly
authorized Windows host. CI_OR_REMOTE_RUNNER provides synthetic independent
checks, not host action receipts. Providers are not hosts.

Local deterministic tests:

    python -m pytest -q tests/test_local_asset_lifecycle.py tests/test_ownership_reducer.py tests/test_disposition.py
    python -m json.tool harness/contracts/local-asset-lifecycle.v1.json

Before merging, reconcile current main, overlapping PR #71 (learning
discovery, draft) and #64 (stewardship orchestration, open), test review
and runtime effects. No copy of private local file listings is admitted
to the public repository.

**Parent outcome remains open** until FileSteward's normal local UI/queues
can consume live, bounded safe-adapter evidence and show these labels,
missing evidence and legal operator choices, validated against actual
operator-approved local paths and protected control cases. This first slice
is a callable classifier + authoritative contract, not a claim that
automatic user-drive classification or UI integration already exists.
