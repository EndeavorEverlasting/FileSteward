# Local antivirus inspection

FileSteward owns the detector's scope, signature trust and human-review
queue. The first inspection mode compares SHA-256 digests against an
operator-approved set. Normal inventory still uses its metadata-only path.

## Approve a local profile

From the FileSteward development checkout, install the optional extra with
`python -m pip install -e ".[antivirus]"` using Python 3.12 or newer.
Use a private, unsynced checkout and a dedicated interpreter if an OS job
will invoke the detector.

```text
filesteward antivirus configure --root ABSOLUTE_LOCAL_DIRECTORY --public-key RAW_ED25519_PUBLIC_KEY_HEX --bundle LOCAL_SIGNED_BUNDLE
filesteward antivirus check --profile PROFILE_ID
filesteward antivirus run --profile PROFILE_ID
filesteward antivirus review --profile PROFILE_ID
filesteward antivirus signature-update --profile PROFILE_ID --bundle NEW_LOCAL_SIGNED_BUNDLE
```

`configure` approves one directory and one signer. Keep the returned opaque
profile ID for manual runs or the scheduler. Scope is bound to the directory
identity. Moving the scope to a new path, replacing the directory, or changing
the signing key calls for a newly approved profile.

The detector reads the immediate eligible regular files in the approved
directory on Windows and native Linux. Subdirectories, links, reparse
points, and cloud placeholders are excluded. Linux admits supported local
filesystems. Hard links, unreadable files, files changed during scanning, and
resource ceilings produce incomplete coverage. Ceilings are 64 MiB per file,
512 MiB per run, 10,000 enumerated entries, and 60 seconds of scan time.
The scheduler also bounds the whole subprocess.

## Signature trust

A local bundle is a UTF-8 JSON envelope with `schema_version` set to
`filesteward.signature-envelope/v1`, a base64 `payload` and a base64
Ed25519 `signature` over the exact decoded payload bytes. The payload is a
UTF-8 JSON object with `schema_version` equal to
`filesteward.sha256-signatures/v1`, a positive integer `sequence`,
and a nonempty `sha256` array of unique lowercase 64-character digests.
The public key is the raw 32-byte Ed25519 key in lowercase hex. Obtain
the key through a separately trusted channel and keep the private signing
key outside FileSteward.

FileSteward verifies the bundle at approval, scan and update. It accepts a
strictly higher sequence from the approved signer and commits the signed
payload and sequence in one transaction. A failed update leaves the current
bundle active. Imports run offline. A copied-back copy of the entire local
profile database is outside this replay protection, so treat the profile
database as trust state when restoring backups.

## Evidence and decisions

| FileSteward observation | Judgment |
| --- | --- |
| Exact hash match | Write `EXACT_SHA256_MATCH` and `HUMAN_REVIEW` with the observed path, digest, bundle version and observation time. |
| Complete scan without a match | Coverage is complete for this scope and bundle. File safety remains undetermined. |
| Partial scan, with or without a match | Retain observed matches while the original directory identity can be confirmed. Report incomplete coverage. |
| A file moves, changes, or stops matching a later bundle | The previous item remains historical evidence. Check the current file and applicable signature before deciding. |
| Invalid signature or changed scope | Reject the policy before reading scan contents. |

Review items are deduplicated per profile, path and digest. `review` emits
private evidence for the local operator. Keep this output and the profile
database out of shared logs, sync folders and version control. In a
development checkout the database is in ignored `var/antivirus`.
Quarantine and deletion require independent action approval and the
applicable FileSteward execution gate. Detector evidence carries no mutation
authority and cannot enter a cleanup plan as an approved action.

## Scheduler contract

SysAdminSuite may run a FileSteward profile through its installed interpreter
using Python isolation and `-m filesteward.cli antivirus run --profile PROFILE_ID`.
The same invocation with `check` validates profile policy and directory
identity before registration. Both commands are quiet for a well-formed
invocation. Consume only the process exit status.

| Exit | Meaning |
| ---: | --- |
| 0 | Check succeeded or scan completed, with either outcome for match evidence. |
| 1 | Local state unavailable. |
| 10 | Scan coverage incomplete, with either outcome for match evidence. |
| 12 | Local policy rejected. |
| 13 | Optional antivirus dependency unavailable. |

Matcher source and regression cases originated in
[SysAdminSuite #571](https://github.com/EndeavorEverlasting/SysAdminSuite/pull/571).
