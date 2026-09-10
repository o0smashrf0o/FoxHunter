# Development Workflow — Fox Hunter

## Clone & Setup

1. `git clone <repo-url>` then `cd SmashDeck`
2. `./foxhunter-launch --dev` — launches Flask on `:8080` + kiosk
3. `python3 -m utils.hardware_checks` — verify required tools (python3, iw, ip, rfkill, kismet, nmap)
4. Capability gate checks against `config/tool_capabilities.yaml`

## Daily Development

1. Create a branch: `git checkout -b feature/foo` (per AGENTS.md: `feature/*` naming)
2. Hack — write code, add detectors, update fingerprints
3. Run checks: `scripts/test.sh` and `scripts/lint.sh`
4. Commit per conventional format: `git commit -m "feat: concise description"`
5. Push and open a PR after reviewing the diff and recording local validation results.
6. Treat a non-zero lint result as a failure unless it matches the documented
   known-error baseline and the change does not add or suppress type errors.

## Current Validation Baseline

`scripts/test.sh` is the project test wrapper. It currently exits successfully
with an informative message when the repository has no `tests/` directory.

`scripts/lint.sh` uses `mypy --ignore-missing-imports utils/` when mypy is
available. At the initial workflow baseline, mypy reports 15 existing errors
across 7 utility modules. The script intentionally returns a non-zero exit
code when those errors are present; they are known technical debt and are not
silently suppressed.

When mypy is unavailable, `scripts/lint.sh` falls back to compiling Python
source files with `python3 -m py_compile`. A successful fallback check verifies
syntax only; it does not provide type-checking coverage.

## Release

1. Update `VERSION` and `CHANGELOG.md` for the planned release.
2. Run `./scripts/test.sh` and record the result.
3. Run `./scripts/lint.sh` and confirm that any findings do not exceed the
   documented known-error baseline.
4. Run `./scripts/make_release.sh --zip` to produce clean install media from
   the repository.
5. Verify the release zip excludes `.venv`, `/data`, `/dist`, secrets, logs,
   captures, and other runtime-generated output, while including required
   `config/`, `scripts/`, `docs/`, and `packaging/` resources.
6. Install and test on the Raspberry Pi CyberDeck using
   `./foxhunter-gui --install`.
7. Validate kiosk startup, dashboard access, hardware checks, and relevant
   connected radio/device behavior on the physical target.
8. Record the exact commit SHA, hardware configuration, and results in
   `docs/test-log.md`.
9. Tag only the validated commit:
   `git tag -a vX.Y.Z -m "Release X.Y.Z"`
10. Push the branch and annotated tag:
    `git push origin main`
    `git push origin vX.Y.Z`