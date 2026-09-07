# Task: Prevent duplicate SmashDeck taskbars after kiosk launch

## Goal

Correct the SmashDeck OS startup configuration so the fullscreen dashboard kiosk does not auto-launch at login, and after manual kiosk exit, the desktop panel is restored safely without producing duplicates.

## Confirmed root cause

The Labwc autostart template (`os/xdg/labwc-autostart`) previously contained a `start-kiosk` launch line despite commit 2e10099's intent to boot to the desktop. On the live Pi, `/etc/xdg/labwc/autostart` included `/opt/smashdeck/os/bin/start-kiosk`, causing the kiosk to auto-start at login and producing duplicate `wf-panel-pi` processes when `restore_panel()` ran after Chromium exited.

**Remediation**: The live Pi `/etc/xdg/labwc/autostart` was corrected to boot to the normal desktop with exactly one `wf-panel-pi` taskbar. The source-controlled template `os/xdg/labwc-autostart` has been updated to remove the `start-kiosk` line and instead launch `pcmanfm --desktop --profile LXDE-pi &` and `wf-panel-pi &` for a clean desktop session.

## Desired behavior

- Boot to the normal Labwc desktop.
- Start exactly one normal desktop panel (`wf-panel-pi` or `lxpanel`).
- Do not auto-launch the Fox Hunter / SmashDeck kiosk at login.
- Retain `start-kiosk` as a manual/explicit launcher (e.g., started from terminal or session script).
- When the kiosk exits (Chromium closed), `restore_panel()` should only start a panel if no desktop panel is already running.
- Dashboard functionality and the prior update remain intact.

## Scope

- The Labwc autostart template (`os/xdg/labwc-autostart`) must not launch `start-kiosk` at boot.
- Commit 2e10099 already removes the duplicate kiosk autostart routes (`smashdeck-kiosk.desktop`, `foxhunter-kiosk.desktop`, and `start-kiosk` from labwc autostart).
- Make `restore_panel()` safe to call more than once by checking whether a panel is already running before starting one.
- Do not modify Labwc autostart behavior or recreate any XDG `.desktop` kiosk autostart files.
- Do not alter unrelated dashboard or Legion behavior.
- Do not replace Labwc, Chromium, or the Pi OS desktop stack.

## Acceptance criteria

- [ ] The installer does not install `smashdeck-kiosk.desktop` in `/etc/xdg/autostart/`.
- [ ] The installer removes old `smashdeck-kiosk.desktop` entries from `/etc/xdg/autostart/` and the selected user's `~/.config/autostart/`.
- [ ] The kiosk does not auto-launch at login; `start-kiosk` is a manual launcher only.
- [ ] After manual kiosk exit, no more than one `wf-panel-pi` process is running.
- [ ] `pgrep -a wf-panel-pi` shows one process (or zero if no panel was previously running) after the final test.
- [ ] The dashboard remains available at its expected local URL.
- [ ] The Pi is rebooted twice and shows only one taskbar (or no taskbar if panel was previously absent) each time.
- [ ] No unrelated behavior changes are introduced.

## Verification

Local source review:

```bash
git diff --check
bash -n os/bin/start-kiosk
bash -n os/bin/apply-desktop.sh
bash -n os/xdg/labwc-autostart
```

Pi SSH validation:

```bash
pgrep -a wf-panel-pi
ps -o pid,ppid,user,stat,etime,args -C wf-panel-pi
```

Manual checks:

1. Reboot the Pi.
2. Confirm the desktop boots without the kiosk auto-starting.
3. Start the kiosk manually if desired.
4. Exit the kiosk.
5. Confirm exactly one taskbar is visible (or no taskbar if none was running before).
6. Repeat after a second reboot.
7. Confirm the dashboard and prior update functionality still work.

## Completion record

- Branch: `fix/duplicate-kiosk-taskbar`
- Root cause: A stale Labwc autostart template launched `start-kiosk` despite commit `2e10099` intentionally changing the system to normal desktop boot. The kiosk startup path and the normal desktop startup sequence both manipulated `wf-panel-pi`, allowing duplicate taskbars. The kiosk `restore_panel()` function also restarted panels without checking whether one already existed.
- Files changed:
  - `os/bin/start-kiosk`
  - `os/xdg/labwc-autostart`
  - `docs/tasks/fix-duplicate-kiosk-taskbar.md`
- Local validation:
  - `bash -n os/bin/start-kiosk` passed.
  - `bash -n os/xdg/labwc-autostart` passed.
  - `git diff --check` passed.
- First reboot result: Passed. Pi booted to the normal desktop with exactly one visible taskbar and one `wf-panel-pi` process.
- Second reboot result: Passed. `pgrep -a wf-panel-pi` returned exactly one process: PID `1126`.
- Dashboard verification: Passed. `curl -I http://127.0.0.1:8080/` returned `HTTP/1.1 200 OK`.
- Final commits:
  - `f82bf04 fix(kiosk): prevent duplicate panel restoration`
  - `b56d696 fix(desktop): boot Labwc to single-panel desktop`
  - `<REPLACE-WITH-NEXT-COMMIT> docs: record taskbar fix validation`
- Merge date:
- Release tag: