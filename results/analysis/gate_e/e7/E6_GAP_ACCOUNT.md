# E6 gap account: 17:48:16 → 19:36:53 on 2026-10-05, and the journal-clock anomaly

Read-only (Gate C2-APPLY Phase 2a). Sources: the persisted systemd journal, boot `a1d2b7e8…` (the E6 boot,
`journalctl -b -1` as seen from the 2026-10-07 boot), and `e6/E6_STATUS.md`. Times are +03 as printed by the
journal after the clock correction described in §3.

## 1. What happened (from the journal)

| time | event |
|---|---|
| 17:38:51 | Phase 0 start (E6_STATUS). |
| 17:48:07 | `sudo systemctl isolate multi-user.target` (the **only** isolate-to-multi-user in this boot). `graphical.target` and `gdm` stopped. |
| 17:48:16 | Phase-4 table collection started: `rmmod nvidia_uvm`, then `insmod …nvidia-uvm-specasync-NEW-e0.9a2-fixed.ko specasync_policy=0 specasync_log_enabled=0 …` (the verified module, srcversion 5997D238…; kernel log `specasync: init OK log_enabled=0 policy=0`; trace ring 4,194,304 slots). Two `dmesg` reads follow. |
| 17:48:18 | `user@1000.service` is stopped (a consequence of the isolate): the GNOME user manager, the VTE child (gnome-terminal) and the tmux pane run from it are told to stop. |
| 17:48:23 | `user@1000.service: State 'stop-sigterm' timed out. Killing.` SIGKILL to systemd (pid 2478), `bash` (5633) and **`tmux: server` (5632)**. This killed the interactive session that was running the E6 work. |
| 17:48:37 → 19:35:51 | **Nothing user-driven.** 360 journal lines in 17:48:16–19:36:53, of which about 30 are cron session lines and the rest are timers and D-Bus-activated daemons (udisks2, upower, fwupd at 18:02; a snapd configure hook at 18:35). No sudo, no module load or unload, no benchmark. |
| 19:35:51–19:35:54 | A console `login` for `rayenchikhaoui` (logind session 22); user manager 13051 starts. |
| 19:36:03 | A new tmux pane (the user reconnecting; "continue now I have connected to the device using tmux"). |
| 19:36:10–19:36:29 | `gh auth` activates `gnome-keyring`; the keyring system prompter fails repeatedly (no desktop). This is the headless keyring problem recorded earlier, again. |
| 19:36:53 | `rmmod nvidia_uvm`, `insmod …e0.9a2-fixed.ko …` (table-collection start again), again at 19:36:58. |
| 19:37:34 → 19:42:41 | The E3a-2 module loads and the smoke/sweep runs (E6_STATUS: tables 19:37:32, smoke 19:38:55, Family 1 19:39:43–19:42:41). |
| 20:06:04 | `sudo systemctl isolate graphical.target` (the GUI restore asked for after the session). |
| 20:17:08–20:17:11 | Shutdown (reboot). |

## 2. Why "isolated" is logged twice

- **First entry (17:48:16, "Phase 4: isolated; platform re-checked …")** records the real isolate (17:48:07).
  That isolate **killed the session that was running E6** at 17:48:23 (the known isolate-versus-desktop
  hazard: the tmux server lived under the GNOME user manager). Table collection had just started and died with it.
- **Second entry (19:36:53, "Phase 4: isolated to multi-user.target (exit 0) …")** was written after the user
  reconnected. **The journal has no `systemctl isolate` command at 19:36:53, or anywhere between 17:48:07 and
  20:06:04.** The machine was already in `multi-user.target` from 17:48:07, so the second isolate either was a
  no-op that was not journaled or did not run; the journal cannot distinguish them. The log line's
  "(exit 0)" cannot be matched to a journal record. **Unresolved; no effect on the data** (see §4).

## 3. The journal-clock anomaly: explained

- `journalctl --list-boots` shows the E6 boot as starting 2026-10-05 **20:27:54** and ending **20:17:11**
  (end before start), and the current boot as starting 16:44:57 on a day the wall clock reads 13:55.
- Cause: in each of the last two boots (`a1d2b7e8…`, `e81fe98c…`) the realtime clock **stepped back by
  10,801 s (3 h 0 min 1 s) at about 35–37 s of uptime**, when `systemd-timesyncd` made its initial NTP
  synchronisation (`Initial clock synchronization to … 13:45:29`; journald: "Clock change detected").
  Entries in the first ~35 s of those boots carry timestamps 3 h too late; everything after is correct.
  Boots in September (`5f825cf7…`, `235bb163…`, `1342730f…`) show no step.
- So E6's real start of boot was 17:27:54 and the 20:27:54 in the boot listing is wrong by exactly +3 h.
  All timestamps used in this account and in `D6_RAW_INVENTORY.md` rows 11 and 13 are from September boots
  or from after the step, so they are **not** affected; only `--list-boots` start times of the two latest
  boots are.
- Not established: why the clock started 3 h ahead. The RTC currently reads correct UTC
  (`timedatectl`: RTC 10:55, local 13:55, "RTC in local TZ: no").

## 4. Consequences for E6

- The gap was an interrupted session plus a wait for the user, not a measurement. Nothing was run in it.
- Every E6 run reloads and verifies the module (`rmmod`, `insmod`, srcversion read-back), so the module
  that happened to be resident during the gap (the verified specasync module, loaded 17:48:16) cannot have
  affected a run.
- **Discrepancy:** at 19:36:53 `E6_STATUS.md` records "loaded stock 6284DA42 (refcnt 0)". The journal shows
  the verified specasync module was loaded at 17:48:16 and **no unload before 19:36:53**, so the module resident
  at that moment was most likely the verified specasync module, not the stock one. Unresolved from the journal
  alone (srcversion reads are not journaled). It does not change any result.
- The E6 sweep itself was 19:39–20:02 (Family 1 end 19:42:41; Family 2 19:45–20:02), inside the 3 h cap
  (cap 20:38:51).
- **Lesson for E7:** `systemctl isolate` from inside a desktop-attached terminal kills that terminal. E7's
  Phase 4 must be run from the existing tmux/console session that is **not** under the GNOME user manager, or the
  run must be started by a script detached from the session (`setsid`/`nohup`) before the isolate.
