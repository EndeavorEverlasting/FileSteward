# Workstation Performance Profiles (local-only v1)

This is the workstation observation component of FileSteward, distinct from the
scan / review / exact-manifest / approve / delete lifecycle. The profile has NO
action-authorizing interface. No scanner or deletion code was changed.

## Capture on each workstation

Run from the proven canonical checkout. For CPU/RAM sampling, install the optional extra in the proven Python environment:

    python -m pip install -e '.[profiles]'

Then capture and inspect:

    python -m filesteward.profiles capture --host-key PTop --volume 'C:\'
    python -m filesteward.profiles show --host-key PTop
    python -m filesteward.profiles compare --host-key PTop

Read-only history/decision-support projection (never delete authority):

    python -m filesteward.visualization.performance --host-key PTop
    python -m filesteward.visualization.performance --host-key PTop --format text

Change host-key to the alias of the actual machine; never assume PTop and
another workstation are interchangeable. The agent must verify local hostname,
git checkout and runtime before claiming a profile belongs to a given host.

Snapshots append to ignored var/profiles/ALIAS/snapshots/*.json; identity.json
binds the alias to a salted digest of platform name, and latest.json is the
atomic latest projection. Capture is serialized per host with .capture.lock. A stale lock after a crash
blocks future captures until the operator verifies no collection is running;
do not automatically clear it based on age.

These paths may contain private workstation
information and MUST NEVER be committed or uploaded. The salted name binding
protects against ordinary cross-host mistakes; it is NOT secure hardware
attestation and does not prove a machine has not been cloned or renamed.

Explicit selected volumes only. Collection reads capacity and, when optional
psutil is available, a short 0–5 second CPU-utilization and RAM sample.
Without psutil those measurements remain null with explicit explanations.

On Windows, `media_type` may be filled only through a fail-closed CIM
physical-to-volume mapping (`profiles/windows.py`): logical disk → partition →
disk drive index → `MSFT_PhysicalDisk.MediaType` (SSD/HDD/SCM). Unspecified,
ambiguous, multi-volume disagreement, missing PowerShell/CIM, or non-Windows
hosts leave `media_type` null with an explicit `missing_metrics` reason. The
collector never invents labels and never persists SMART serials or model
strings into profile metrics. Thermals, disk I/O latency, and wear remain
unverified; no values are fabricated. Samples are point-in-time observations,
NOT comparable performance benchmarks without the same workload and conditions.

Capacity is CRITICAL below 10% free, BELOW_TARGET at 10–under 20%, and
AT_OR_ABOVE_TARGET at least 20%. This is operational visibility, NEVER
cleanup authorization. Protection and owner relationships override all
performance/capacity pressure. The prior Wispr Flow installation incident
makes application-serviceability protection non-negotiable.

## P97: verified prior art / disposition

- Glances (https://github.com/nicolargo/glances): cross-platform sample
  collection and modular optional data sources. ADAPT lightweight optional
  collection; REJECT auto-activating a network listener or service.
- osquery (https://github.com/osquery/osquery/blob/master/specs/system_info.table):
  typed hardware fields separate from observation tables. ADAPT schema-first
  inventory; REJECT persisting hardware serials in tracked artifacts.
- windows_exporter (https://github.com/prometheus-community/windows_exporter):
  independent CPU, memory and logical-disk collectors. ADAPT Windows opt-in
  collectors with volume binding; REJECT inferring C:-specific I/O counters
  from unmapped physical-disk readings.

Do not copy third-party code without compatible license/provenance verification.

## P82 experiment admission

Hypothesis: local append-only observations with explicit missing-data states
are sufficient to establish capacity baselines without risking installed apps.
Comparator: same workstation/volume/workload at repeated timestamps, with
and without psutil. Falsifier: identity bleed, overwritten history, a missing
measurement masquerading as zero, or cleanup authority derived from a profile.

Current validation: synthetic unit tests only. The real PTop and Admin Box 1
host performance values, drive hardware mapping and capture reliability have
NOT been measured by the repository authoring environment.

Downstream: Windows opt-in collectors, CPU/disk sample provenance and
p50/p95 I/O measurements, physical disk mapping, protected app detection,
trend comparison, dashboard projections, scheduler, host runtime smoke tests.
