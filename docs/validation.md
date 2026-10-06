# Desktop validation

The detailed commands, prerequisites and guest setup are in
[Workspace State's test guide](https://github.com/Sage-Cat/workspace-state/blob/main/docs/testing.md).
This page records the combined test scope and what the results prove.

## Run the checks

Requires Linux, Python 3.11+, Node.js 20.19+, npm, Make, Git, GNOME Shell 46,
`gdbus`, `dbus-run-session`, `glib-compile-schemas`, Python GTK 3 bindings,
`jq`, `shellcheck`, `unzip`, ESLint and tmux.

Start from a recursive clone with clean components at their recorded commits:

```sh
npm --prefix login-hud ci
make check
make integration EVIDENCE_DIR=/tmp/desktop-validation
```

`make check` runs pin/privacy checks and component suites. `make integration`
starts disposable GNOME sessions for window placement and HUD tests. Neither
command reboots the host or runs cleanup against personal data.

The full QEMU lifecycle test is separate. It requires a disposable Ubuntu
installation with GNOME/Wayland and the real applications installed. Do not run
its power-off fixture on a working desktop. CI's headless checks are not a
substitute for the guest shutdown/boot tests.

## Strict standalone save: 2026-10-07

Manual save now checks current shutdown/recovery ownership before capturing or
writing, including cancellations that occurred before application draining.
An explicit `save --verify-idle-codex` can identify older idle native clients
through a bounded `/status` diagnostic. Automatic saves never type into panes;
uncertain identity or changed ownership preserves the prior checkpoint.

Component `7c24ff96d74941d74bd439cd12523183a792c64b` passed 1,286 Python tests
and the browser/editor protocol suites. Its runtime content digest is
`56b1327dd9812eb50867d823b66bfe0b27eab84be6c9925557439f5903507be8`.
All eight public runtime content digests match the tested guest candidate
`r-be0d082bd04b3a52b15a5391`.

Three real strict saves preserved 25 native windows, ten tmux sessions, seven
Chrome windows, 42 tabs and three groups. All five categories were fully
captured and adopted without retained recipes or warnings. Raw browser IDs,
group membership, native placement, tmux names/layout/geometry, processes and
selection remained unchanged; HUD and completion receipts were unchanged too.
The staged candidate was invoked separately from the guest's older active
coordinator. There was no shutdown, application restart or corrective move.

Real native CLI 0.160.1 tests cover no-alt-screen 159×37 and 80×37, and seeded
alternate-screen 319×76. A smaller alternate-screen repeat that is byte-identical
to historical output deliberately refuses; it is not counted as an identity
proof. Drafts, active turns, resizing and changed PID/TTY ownership also refuse.
Status controls use a private loopback provider with zero inference requests.
The desktop-scale conversation workers remain synthetic.

See [commands, native limits and the standalone guest harness](https://github.com/Sage-Cat/workspace-state/blob/main/docs/testing.md#standalone-save-during-cancellation-recovery).
Source/CI, guest validation, scheduled installation and code already running in
a desktop are separate results. This update does not claim another host login
or another power-off cycle; the earlier real cold-boot cycles remain below.

## Terminal identity, names and Nemo deadlines: 2026-10-06

Four host conversations were manually resumed by their exact UUIDs in existing
panes. The user chose to keep the current host layout. Fresh daemon-backed CLI
clients had lacked a provable saved identity; they now have a conservative
launch-time thread-title adapter, with visible refusal for unsupported cases.
New tmux creation preserves pane order, literal names, rename policies and saved
layout. Existing panes require identity proof before naming changes.

The final component suite passed 1,236 Python tests and browser/editor protocols.
Private native tests passed on both host and guest, including real CLI 0.160.1
and 0.160.0 fresh-thread and `/new` binding without authentication or inference.
The scale workload still uses 23 synthetic workers; it does not prove account
conversation recovery.

The first real names cycle passed all terminal checks but failed the whole
desktop due to Nemo's shared timeout. Regression tests reproduced an expired
placement-lock wait with no issued move. Per-window budgets now retain the
operation deadline, bounded waits and ownership checks. The unchanged failed
guest then passed genuine GNOME shutdown, cold boot and the full 25-window
oracle on `r-527d1ba937b3924da3065b5f`, without preparatory save or corrective
placement. Its HUD countdown measured 5.009 seconds. Failed and successful
trials are recorded separately. The following ordinary cycle also passed the
complete oracle without save, fixture mutation or corrective moves; its
countdown measured 5.012 seconds. Commands and limits are in the
[terminal test record](https://github.com/Sage-Cat/workspace-state/blob/main/docs/testing.md#terminal-identity-and-names-2026-10-06).

Published component revision:
`ee9e791a6b5fb4d3e4839f59e92ccb7904a6b683`. Its packaged runtime digest is
`faa72fa369ce5705cbe46973fae7a309ecbc830421510c534c2063513babd865`.
All eight staged component content digests match the final tested guest release;
the different release IDs also encode Git provenance. Umbrella `make check`
and isolated integration passed, including six placement and 21 HUD cases.
Host deployment is scheduled for next login; no active host application or
tmux layout was restarted or changed to activate this build.

## Capture provenance and repeat boot: 2026-10-06

The retained recipe was not lost. Its newer complete browser observation was
incorrectly rejected when shutdown capture took more than one second. A later
terminal autosave could remove that original context. Captures now bind UUID,
completion time and payload digests; old hook-stripped evidence requires a unique
matching original private history publication. Unsafe or ambiguous evidence
still refuses recovery instead of guessing or replacing windows.

Workspace State runtime `5bad729` passed real KVM trials with the same 25-window,
seven-browser/42-tab/three-group, ten-tmux workload described below:

- Legacy slow capture → new release → cold boot: exact restoration, measured
  capture gap 5.986818 seconds.
- New capture → three native calls returning pending → cold boot: exact
  restoration and later verified placement, measured gap 7.490238 seconds.
- Partial application drain → actual HUD Cancel → settled native jobs → retry:
  sealed checkpoint/tmux bytes survived a real autosave; cold boot restored the
  complete desktop without manual reconstruction.
- Ordinary next shutdown and cold boot: exact continuity passed without fixture
  mutation, manual save or corrective placement.

The old runtime separately reproduced pre-launch refusal with a genuine
2.878779-second capture. Its original synthetic profile retained the tabs and
groups. The history-only compatibility test used this real producer output but
was a read-only consumer check, not an additional full cold-boot trial.

Local checks passed 1,134 Python regressions plus browser/editor protocols.
Independent native checks passed nine placement/companion and 21 HUD cases;
umbrella integration passed six placement and 21 HUD cases. The full procedure,
evidence requirements and limitations are in the
[capture-binding test record](https://github.com/Sage-Cat/workspace-state/blob/main/docs/testing.md#capture-binding-2026-10-06).
README files retain only setup, use and documentation links. No private runtime
logs, profiles or per-run identifiers are published.

## Delayed placement and shutdown settlement: 2026-10-05

The earlier short HTTP delay did not cover a native restore call returning with
pending content. A loopback fixture now releases responses only after three
production calls return pending. The old runtime reproduced verified content
with failed placement and no compositor request. The fix submits an owned first
placement only after exact native content and group checks succeed.

| Check | Result |
| --- | --- |
| Unfixed `437b038` cold boot | Expected regression; kept as a failed product trial |
| `7c02d04` cold boot | Three pending windows reached verified content and placement |
| `79465c0` integrated cold boot | Same pending path and complete inventory/placement passed |
| Ordinary `79465c0` → `887e593` | Clean GNOME shutdown and exact cold-boot continuity passed without fixture mutation |
| Native portal stop-job latency | A 35-second VM-only stop gate exceeded the deadline; handoff was withdrawn and ownership held until settlement |
| Isolated GNOME | Nine placement/companion and 17 HUD cases passed |
| Adverse identity and ownership | Changed content, ambiguous matches and stale continuation owners refused without loss or moves |

Both positive pending trials preserved seven Chrome windows, 42 synthetic tabs,
three groups, 25 native windows, ten tmux sessions and 23 synthetic workers.
They used real GNOME power-off, HUD countdown, QMP guest shutdown, cold boot and
Ubuntu login. No measured manual save or corrective placement produced the pass.
Those earlier pending trials kept Chrome on workspace/display 0; the remaining
application windows covered the other workspaces/displays. Scattered-browser
checks on the later candidate are recorded separately.

The document portal now has a native stop and settlement receipt before GNOME
handoff. Tests distinguish issued jobs from pre-issuance cancellation and keep
ownership until outstanding work settles. This coordinates Ubuntu's five-second
user-manager shutdown deadline; it does not prove which historical internal FUSE
call blocked. Account data and physical-monitor behavior remain outside the
guest coverage described below.

A further real early-cancel trial verified completed native job settlement,
unchanged sealed checkpoint/tmux bytes and actual autosave deferral. Its retry
refused a missing VS Code owner proof. The shared migrated-main helper now
supports exact editor recovery/project units with the existing live executable,
parent/child, user and PID/start-time proof. The old failure is retained; service
success is not treated as proof that no editor children were forcibly stopped.

The same trial exposed a stale HUD commit overlay after completed cancellation.
The new HUD clears matching terminal markers and permits shutdown progress only
under current readiness/authority. All 55 Node checks and 18 isolated real HUD
checks passed. Coordinated VM acceptance uses both fixes together.

The scattered-browser retained replay on Workspace State `4f81992` / HUD
`8522da1` passed delayed content, placement and the complete 25-window inventory.
Its early-cancel retry then exposed three application checkpoint stages left
pending by the reuse branch. HUD correctly withheld its countdown. The worker
now publishes all inherited category stages and preserves original degradation;
the old failure is retained, not relabeled.

Scoped settled failures now report recovery completion accurately in HUD and
its diagnostic endpoint. The current source checks passed 1099 Python tests,
browser/editor protocol checks and 58 HUD tests. Real isolated GNOME passed
21 HUD cases, including Cancel → Close → a fresh completed retry and refusal
to acknowledge an overall-ready report with a pending category.

Final acceptance used Workspace State `08ca75b` and HUD `afa9f9e`, immutable
guest `r-d756f13c30309fc2f0b977d4`. All four lifecycle trials passed:

| Final trial | Result |
| --- | --- |
| Ordinary upgrade | Exact 25-window state; clean shutdown/cold boot; 5.022-second countdown |
| Retained/degraded recipe with delayed native content | Three pending returns continued to verified placement; seven Chrome windows/42 tabs/three groups preserved |
| Early Cancel and protected retry | Cancel at 3.270 seconds; native jobs settled; actual autosave retained sealed bytes; new 5.062-second countdown; full cold-boot restore |
| Ordinary next cycle | Exact inventory/content/placement without fixture mutation, save or corrective moves; 5.004-second countdown |

The last three use the same runtime throughout. Chrome spans six workspaces
and three virtual displays. Native content/group/window continuity, scoped
receipts, genuine GNOME confirmation, QMP shutdown/EOF and clean user-manager
stop are required. The actual running Chrome worker revision was checked.
The editor's migrated-main helper completed without child SIGKILL. The VM-only
35-second portal gate tests native stop-job latency, not the unidentified
historical internal FUSE call. No reconstruction or relaxed failed-attempt
verifier created a pass; the intermediate worker upgrade is recorded separately.

Full SHAs, methodology and coverage limits are in
[the final component matrix](https://github.com/Sage-Cat/workspace-state/blob/main/docs/testing.md#final-coordinated-vm-acceptance).
Documentation-only commits preserve the tested packaged source digests. The
host receives next-login-only deployment; that actual host login is not a VM
test result. README remains a short setup/install entry point.

## Retained-checkpoint upgrade: 2026-10-04

Runtime candidate Workspace State `437b03872110790b4a3ae86ebe89221081235973`
fixes the first-login transition from an old retained browser recipe to a newer,
intact native session. The old recipe has six windows and 38 tabs; the real
browser has seven windows, 42 tabs and three groups. There is no preparatory
manual save or automatic baseline adoption.

| Check | Result |
| --- | --- |
| Source suite | 964 Python tests plus browser/editor companion checks passed |
| Isolated GNOME | Six placement and 17 HUD cases passed |
| Unfixed `ef24480` cold boot | Reproduced the failure; kept as `passed: false` |
| `ef24480` → `437b038` | Full shutdown, cold boot and login passed; 25 native windows and complete content/placement verified |
| Same-release retained replay | Passed with real HUD cancellation/retry and all 42 HTTP responses delayed at least three seconds |
| Adverse reconciliation | Five real companion/production-validator probes refused changes without content or identity loss |
| Terminal autosave | Two actual save hooks retained original capture evidence and reconciliation eligibility |
| Ordinary continuity | Third real shutdown/cold-boot cycle passed without fixture reset or manual save; healthy shutdown captured the complete new baseline |
| Real signed-out CLI | Authentication screen verified again on the final boot in an existing Alacritty/tmux client |

Full cycles require clean native browser exit before Shell, user-manager stop,
QMP guest shutdown/EOF, scoped receipts and exact restored inventories. A
historical `cd42271` → `723de36` run fixed browser reuse but failed the complete
cycle due to old teardown behavior and inconsistent viewer-fixture placement;
it is not counted as a passing upgrade.

The component test guide records the fixture, commands, evidence and limits.
The signed-out workload and host-versus-guest limitations below still apply.
Documentation-only commits after the candidate do not imply extra runtime tests.

## Recorded validation: 2026-10-03

The runtime tested used Workspace State `ef24480e0974442fedb6c100be67c9bfbe84826b`
and Login HUD `f1026fa520b863e8a87703c138943de482edbdf1`, coordinated by parent
`11cc9d73aa05c7c8df99319eaf866e561d876388`. Later documentation-only commits do
not represent additional full VM cycles.

| Layer | Result and scope |
| --- | --- |
| Workspace State | 910 Python checks; browser protocol and editor companion checks passed |
| Login HUD | 53 checks, lint and release-package validation passed |
| Combined checkout | Parent/component `make check` and `make integration` passed |
| Disposable GNOME | 6 placement and 17 HUD scenarios passed |
| Full Ubuntu guest | Three consecutive shutdown, cold boot and graphical-login cycles passed |
| Other components | Their source suites ran in the combined checks; no claim of exhaustive feature testing in the VM |

The guest used Ubuntu 24.04.5, kernel 7.0.0-34-generic, GNOME 46, Mutter 46.2,
systemd 255.4 and QEMU/KVM 8.2.2. It had six vCPUs, 12 GiB RAM, three virtual
displays and six workspaces. Browser/editor and relevant desktop application
versions were aligned with the investigated installation.

The workload contained 25 native windows: six Alacritty windows, seven Chrome
windows, four Nemo windows, one editor, one remote viewer and six desktop
application windows. Chrome held 42 synthetic HTTP tabs in three groups;
ten tmux sessions contained 23 synthetic terminal workers.

Chrome and its companion/native host, Alacritty, tmux, Nemo, the editor,
Remmina, social applications and the viewer were real installed programs.
Account sign-in was not required. A real terminal application was also launched
to its authentication screen in an existing Alacritty/tmux popup. The synthetic
workers test restoration scale and identity; they are not evidence of
account-authenticated session recovery.

## Lifecycle procedure

1. Capture the guest's independent expected content, window placement and process
   identities before changing anything.
2. Exercise a stale browser recipe. Verify refusal leaves native tabs and groups
   unchanged, then record the controlled failed startup state.
3. Run explicit manual save. Keep the original failure evidence, and verify the
   new baseline is accepted.
4. Change browser tabs and terminal state again. The next shutdown must capture
   these later changes, not reuse the earlier manual baseline.
5. Request real GNOME Power Off. Observe the rendered HUD, verified checkpoint,
   approximately five-second countdown and operation-scoped completion receipts.
6. Require clean application closure before Shell teardown, a clean user-manager
   stop, and QMP `SHUTDOWN` with `guest: true`, followed by connection EOF.
7. Start the guest again and establish a new boot and graphical login. Compare
   saved and live content, placement, counts, identities and companion versions.

All three final cycles passed. The second added an actual HUD Escape cancellation
and a new shutdown attempt. Its 42 HTTP pages each took at least three seconds to
respond. Separate retries preserved native browser window/tab/group IDs and
placement without creating duplicates. Browser IDs were compared within one
boot; they naturally change across boots.

## Failures retained during development

- The old implementation reproduced the stale-baseline bug: shutdown kept the
  manual-save browser recipe and missed subsequent changes.
- An earlier candidate passed two cycles, then exposed a real teardown race:
  Shell began exiting before the browser's stop helper ran. The final runtime
  closes verified managed applications before releasing the GNOME handoff.
- A separate guest user-manager timeout exposed terminal shells that survived
  TERM. A scoped terminal HUP policy resolved that reproduced path. This does
  not establish the sole cause of every historical host timeout.
- A stale Remmina agent socket was reproduced with the real snap. The guard
  recovered it while preserving both listening and bound-but-not-listening
  live sockets. The vendor's normal stop status was not hidden.

Failed and intermediate runs were retained separately from final passing runs.
No historical failure was rewritten as a successful startup.

## Evidence and limits

Keep operation receipts, journals, QMP events, expected/manual/shutdown/live
snapshots and native identity observations together in a private evidence
folder. A green HUD or an accepted placement request alone is not a pass.
Review any evidence before sharing: window titles and URLs can be private.
Published fixtures contain synthetic data, not credentials or user profiles.

This validation covers launching programs, restoring synthetic content, tmux
state and native window placement without app account sign-in. It does not
prove authenticated content recovery, live cloud-account synchronization,
Windows guest hibernation or physical GPU/monitor hotplug behavior. The viewer
used a small firmware-only guest, and cloud mounts were synthetic fixtures.
Browser registration used a controlled test setup, so a private-profile upgrade
path still needs its own validation.

Unit tests cover additional late-cancellation, interrupted-worker and ownership
cases; only the described cancellation was exercised as a real full VM cycle.
Cleanup scheduling and deletion were not enabled on personal data. Runtime
installation and root-only integration remain separate from source publication;
checks must report any installation pending authorization rather than claim it
is active.
