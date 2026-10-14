# Mobile storage M0: platform-aware review without mutation

Status: code/contract candidate, not an Android/iOS app. 2026-10-13.

This is a **cross-repository contribution** from EscapeHatch's user-scoped
observational consent/event evidence discipline into FileSteward's existing
owner-aware cleanup judgment. There is no shared deletion or job state engine.

## Supported classification

- **Photos and videos:** Android Photo Picker/MediaStore or iOS PhotoKit
  limited selection. The user reviews content with the system-owned facility.
- **Selected documents:** Android Storage Access Framework or iOS Files
  provider selection; permission is limited to provider scope.
- **Other apps and system data:** protected. Never crawl other app sandboxes
  or delete installation/runtime directories as if they were generic caches.
- **FileSteward's own cache:** regeneration/ownership evidence allows only a
  REVIEW route in this milestone, not delete.
- **Cloud-managed content:** iCloud/Google Photos sync is NOT a proven
  independent recoverable backup. Remote-only or unknown local residency
  yields no reclaim estimate.

The new module `src/filesteward/mobile/policy.py` has no OS access, writes,
permissions or deletion calls. It returns FileSteward's existing
`CleanupDisposition` enum and a safe route. Every decision has
`mutation_authorized=False`, `is_executable=False`, and no reclaim
estimate, even for large inputs.

The desktop scanner/deletion executor remains the desktop owner; content URIs,
PhotoKit assets and provider document handles must never be interpreted as
local filesystem paths.

## Cross-repo donor and bounded integration

- **EscapeHatch → FileSteward:** copy the *pattern* of explicit observation,
  bounded local metadata, visible consent/revocation, and no state promotion from
  an observation. Do NOT copy browser DOM scraping, application question IDs,
  career status, extension permissions, or raw job data.
- **FileSteward → EscapeHatch:** supply the *pattern* of independent evidence
  classification vs authorization and execution; no submission should follow
  merely because the observer witnessed a click or user input.
- Both products own their domain schemas/UX/security gates. The cross-repo
  contract is a versioned *reference*, not a runtime dependency or package.

See `harness/contracts/mobile-storage-capability.v1.json` and
`tests/test_mobile_storage_policy.py`.

## P04 successor graph (M0 done when CI green)

- **M1 Android**, independent: native metadata adapter with scoped picker and
  real-device denied/limited/revoked/cloud-only behavior; no mutation.
- **M2 iOS**, independent: PhotoKit/Files metadata adapter, limited selection,
  iCloud-only behavior, no mutation.
- **M3 convergence:** shared typed evidence semantics and P129 phone-native
  review UX with a single policy owner; P110 viewport + device acceptance.
- **M4 separate authorization:** only owner/OS semantic actions after specific
  recovery and privacy gates; no authority has been granted.

Execution host for M0: CURRENT_CHAT_RUNTIME with GitHub provider writes.
M1/M2 native device proof needs local agents/physical devices. No uncommitted
PTop/DTop state was inspected or altered. Preserve ongoing FileSteward PR #53.

## P82 experiment admission

Hypothesis: one typed non-executable routing contract can cover both mobile OSes,
five storage categories, four permission states and four cloud states without
ever promoting an observation into deletion authority. Baseline: FileSteward
had no mobile module on `main@09597b68`; Windows-only ownership assumptions
cannot classify mobile content handles. Prototype: M0 module only.
Metric: exhaustive 2×5×4×4 = 160 policy combinations, adversarial fixtures,
100% no mutation/no fake reclaim. Rejection: any input yields deletion
authorization, false reclaim, or other-app unprotected state. Stronger claim
blocked until CI reports and actual Android/iOS runtime certification.

Platform authority references:
- https://developer.android.com/training/data-storage/shared/media
- https://developer.android.com/training/data-storage/shared/documents-files
- https://developer.apple.com/documentation/photokit/delivering-an-enhanced-privacy-experience-in-your-photos-app
