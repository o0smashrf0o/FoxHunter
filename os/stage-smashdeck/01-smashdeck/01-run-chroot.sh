#!/bin/bash -e
export SMASHDECK_USER=smash
export SMASHDECK_PREFIX=/opt/smashdeck
export DEBIAN_FRONTEND=noninteractive
# venv + pip deps
if [[ ! -x /opt/smashdeck/.venv/bin/python ]]; then
  python3 -m venv /opt/smashdeck/.venv
fi
/opt/smashdeck/.venv/bin/pip install --upgrade pip wheel
if [[ -f /opt/smashdeck/requirements.txt ]]; then
  /opt/smashdeck/.venv/bin/pip install -r /opt/smashdeck/requirements.txt
fi
# Brand + services (packages already installed this stage)
# apply-os brands the system and enables services (no live restart in chroot)
bash /opt/smashdeck/os/apply-os.sh || true
chown -R smash:smash /home/smash /opt/smashdeck || true
