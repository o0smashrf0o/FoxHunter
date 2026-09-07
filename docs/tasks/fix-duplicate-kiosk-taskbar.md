# Task: Prevent duplicate SmashDeck taskbars after kiosk launch

## Goal

Correct the SmashDeck OS startup configuration so the fullscreen dashboard kiosk does not auto-launch at login, and after manual kiosk exit, the desktop panel is restored safely without producing duplicates.

## Confirmed root cause

Commit 2e10099 ("Do not autostart Fox Hunter; boot to desktop") already removes the duplicate kiosk autostart routes:

- `os/apply-os.sh` no longer installs `smashdeck-kiosk.desktop` or `foxhunter-kiosk.desktop` into `/etc/xdg/autostart/` or `~/.config/autostart/`.
- `os/bin/apply-desktop.sh` and `os/bin/fix-boot.sh` both remove any stale `start-kiosk` entries from `/etc/xdg/labwc/autostart` and user autostart files.
- `os/desktop/labwc/autostart` and `os/xdg/labwc-autostart` no longer launch `start-kiosk` at login.

The remaining defect is that `restore_panel()` in `os/bin/start-kiosk` can unnecessarily kill and restart a desktop panel that was already running before the kiosk started, producing duplicate taskbars when the user manually exits the kiosk.

## Desired behavior

- Boot to the normal Labwc desktop.
- Start exactly one normal desktop panel (`wf-panel-pi` or `lxpanel`).
- Do not auto-launch the Fox Hunter / SmashDeck kiosk at login.
- Retain `start-kiosk` as a manual/explicit launcher (e.g., started from terminal or session script).
- When the kiosk exits (Chromium closed), `restore_panel()` should only start a panel if no desktop panel is already running.
- Dashboard functionality and the prior update remain intact.

## Scope

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
- Root cause:
- Files changed:
- Local validation:
- First reboot result:
- Second reboot result:
- Dashboard verification:
- Commit:
- Merge date:
- Release tag: