# OUI / MAC vendor data (offline)

Local MAC-prefix databases used by `utils/oui_lookup.py` for vendor resolution
on Wi‑Fi, BLE, and Detect results. **No network is used at lookup time.**

| File | Source | Role |
|------|--------|------|
| `manuf` | [Wireshark manuf](https://www.wireshark.org/download/automated/data/manuf) | Primary curated OUI table (~3 MB) |
| `nmap-mac-prefixes` | [nmap](https://github.com/nmap/nmap) `nmap-mac-prefixes` | Secondary / gap fill (GPL) |
| `oui.sqlite` | Built from the above | Runtime DB (~5 MB, 58k+ prefixes) |
| `ieee-oui.txt` / `ieee-oui.csv` | IEEE registry (optional) | Official MA-L dump if download succeeds |

## Update (when online)

```bash
./scripts/update_oui.sh
```

Rebuild SQLite only (from files already on disk):

```bash
python3 -m utils.oui_lookup --rebuild --status
# or
python3 -c "from utils.oui_lookup import build_sqlite; print(build_sqlite(force=True))"
```

## Lookup CLI

```bash
python3 -m utils.oui_lookup DC:A6:32:8C:8F:4F
python3 -m utils.oui_lookup --status
```

API: `GET /api/oui/lookup?mac=AA:BB:CC:DD:EE:FF` and `GET /api/oui/status`.

## Note on IEEE

The official IEEE site often blocks automated clients (HTTP 418). Manuf + nmap
already cover nearly all OUIs used in the field. Re-try IEEE when updating if
you want the registry dump as well.

## Licensing

- Wireshark manuf: redistributed as part of Wireshark’s data; keep for offline use.
- nmap-mac-prefixes: GPL (nmap). Suitable for shipping with this project.
- IEEE: public registry data when obtained from standards-oui.ieee.org.
