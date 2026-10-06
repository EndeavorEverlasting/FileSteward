# U1 P97 — Decision blocker / next-actions prior art

**Capability researched:** Make “I want to delete this” operable or explicitly blocked inside the Atlas Decision Chamber, with actions following selection rather than ceremonial top chrome.

**Local floor:** `deaf9d8` / v0.10.0 proof; `decision_flow.allowed_intents()`; quarantine-first; permanent delete forbidden; offline synthetic report.

## Reference repositories

| Ref | Identity | License | Why in set |
|---|---|---|---|
| WinDirStat | https://github.com/windirstat/windirstat — cleanup strings in `windirstat/res/langs/lang_en.txt`; docs Cleanups | GPLv3-or-later (README) | Selection → cleanup actions in context; recycle-bin vs permanent delete labels |
| ncdu | https://dev.yorhel.nl/ncdu/man — `--confirm-delete`, `--delete-command`, `-r` readonly | MIT | Confirm-before-delete; trash via custom command; readonly mode |
| rclone ncdu | https://github.com/rclone/rclone `cmd/ncdu/ncdu.go` (~b5a81dab) | MIT | Popup cancel/confirm before delete; explicit “Aborted!” |
| BleachBit | https://github.com/bleachbit/bleachbit — TUI confirm commits 9982fe4 / d2b3c21 (2026-06-21) | GPLv3 | Destructive confirm defaults focus to **No** |

## Pattern ledger

| Pattern | Disposition | Note |
|---|---|---|
| Actions follow current selection (WinDirStat cleanup menu) | **ADAPT** | FileSteward: chamber scene next-actions, not header chrome |
| Explicit confirm before destructive op (ncdu/rclone/BleachBit) | **ADAPT** | Confirm staging only; default remains non-destructive |
| Surface blocked delete as readable lock, not silent omission | **ADOPT** | `STAGE REMOVAL PATH — LOCKED` + disposition-specific why |
| Permanent delete / shred | **REJECT** | Violates FileSteward MVP + agent protections |
| Copy WinDirStat/BleachBit source | **REJECT** | License + authority model mismatch |

## Solved vs gap

| Slice | Map |
|---|---|
| Treemap + linked selection | ALREADY_SOLVED_INTERNALLY |
| Legal intents owner (`allowed_intents`) | ALREADY_SOLVED_INTERNALLY |
| Selection-local action panel | AVAILABLE_TO_EMULATE_EXTERNALLY → chamber next-actions |
| Explicit delete-blocker copy for UNKNOWN | PROJECT_SPECIFIC_GAP (closing this pass) |
| Real C: quarantine apply | PROJECT_SPECIFIC_GAP / operator gate (out of offline report) |

## Prioritized development gap (this sprint)

**Target:** Disposition click + Decision Path RESOLVE show operable intents **and** a locked STAGE REMOVAL explaining why delete is blocked for UNKNOWN/HUMAN_REVIEW; header Next Actions stop encumbering Atlas Home; cartouche dodges panels; legend glows on active disposition.

**Owners:** `scene_surface.py`, `decision_chamber.py`, `experience.py`, `shell.py`

**Non-goals:** Permanent delete; live C: byte removal; inventing reclaim authority for UNKNOWN.
