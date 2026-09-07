# Task: Prevent duplicate SmashDeck taskbars after kiosk launch

## Goal

Correct the SmashDeck OS startup configuration so the fullscreen dashboard kiosk starts once and Raspberry Pi OS displays only one `wf-panel-pi` taskbar after the kiosk exits.

## Confirmed root cause

The cyberdeck runs Labwc with one compositor process and two `wf-panel-pi` processes.

The installed SmashDeck OS configuration starts `/opt/smashdeck/os/bin/start-kiosk` through more than one startup mechanism:

1. Labwc system autostart:

   ```text
   /etc/xdg/labwc/autostart
   ```

   runs:

   ```text
   /opt/smashdeck/os/bin/start-kiosk
   ```

2. The SmashDeck installer also creates an XDG autostart entry:

   ```text
   /etc/xdg/autostart/smashdeck-kiosk.desktop
   ```

   and copies it into the active user’s autostart directory:

   ```text
   ~/.config/autostart/smashdeck-kiosk.desktop
   ```

Both routes execute `start-kiosk`. The script calls `restore_panel()` when the kiosk exits, and each concurrent instance can start `wf-panel-pi`. This produces duplicate taskbars.

## Desired behavior

- Labwc starts once.
- The SmashDeck kiosk starts once at login.
- The kiosk runs fullscreen without a panel covering the HUD.
- When the kiosk closes, normal desktop behavior returns with exactly one panel.
- Dashboard functionality and the prior Legion/SmashDeck update remain intact.

## Scope

- Make Labwc autostart the only canonical kiosk launch mechanism for Labwc systems.
- Stop `apply-os.sh` from installing duplicate SmashDeck XDG kiosk launchers.
- Remove existing SmashDeck-owned system and user XDG kiosk launchers during installation.
- Make `restore_panel()` safe to call more than once.
- Update documentation and change history.
- Validate through two cyberdeck reboots.

## Non-goals

- Do not remove the kiosk feature.
- Do not alter unrelated dashboard or Legion behavior.
- Do not replace Labwc, Chromium, or the Pi OS desktop stack.
- Do not modify unrelated desktop autostart entries.
- Do not commit device credentials, operational logs, captures, or generated state.

## Proposed code changes

1. In `os/apply-os.sh`, replace installation of `smashdeck-kiosk.desktop` with removal of stale system and per-user copies.
2. In `os/bin/start-kiosk`, make `restore_panel()` start a panel only if one is not already running.
3. In `os/xdg/labwc-autostart`, document that Labwc is the canonical kiosk startup mechanism.
4. Update this task record and the repository changelog.

## Acceptance criteria

- [ ] The installer does not install `smashdeck-kiosk.desktop` in `/etc/xdg/autostart/`.
- [ ] The installer removes old `smashdeck-kiosk.desktop` entries from `/etc/xdg/autostart/` and the selected user’s `~/.config/autostart/`.
- [ ] The kiosk still starts at Labwc login.
- [ ] After kiosk exit, no more than one `wf-panel-pi` process is running.
- [ ] `pgrep -a wf-panel-pi` shows one process after the final test.
- [ ] The dashboard remains available at its expected local URL.
- [ ] The Pi is rebooted twice and shows only one taskbar each time.
- [ ] No unrelated behavior changes are introduced.

## Verification

Local source review:

```bash
git diff --check
bash -n os/apply-os.sh
bash -n os/bin/start-kiosk
```

Pi SSH validation:

```bash
pgrep -a wf-panel-pi
ps -o pid,ppid,user,stat,etime,args -C wf-panel-pi
```

Manual checks:

1. Reboot the Pi.
2. Confirm the kiosk opens once.
3. Exit the kiosk.
4. Confirm exactly one taskbar is visible.
5. Repeat after a second reboot.
6. Confirm the dashboard and prior update functionality still work.

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
