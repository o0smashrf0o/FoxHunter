#!/bin/bash -e
export FOXHUNTER_USER=smash
export FOXHUNTER_PREFIX=/opt/foxhunter
export DEBIAN_FRONTEND=noninteractive
# venv + pip deps
if [[ ! -x /opt/foxhunter/.venv/bin/python ]]; then
  python3 -m venv /opt/foxhunter/.venv
fi
/opt/foxhunter/.venv/bin/pip install --upgrade pip wheel
if [[ -f /opt/foxhunter/requirements.txt ]]; then
  /opt/foxhunter/.venv/bin/pip install -r /opt/foxhunter/requirements.txt
fi
# Brand + services (packages already installed this stage)
# apply-os brands the system and enables services (no live restart in chroot)
bash /opt/foxhunter/os/apply-os.sh || true
chown -R smash:smash /home/smash /opt/foxhunter || true
