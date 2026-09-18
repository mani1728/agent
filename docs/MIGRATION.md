# Stage 1: canonical repository layout

Baseline: `1a133e6c6ea1b02a039f45610182037d347390ba` on `develop`.
Active source: `Version 0_0_9`. No source, dependencies, tests, configuration,
service host, or packaging recipe from `Version 1_0_0` is activated.

## Path map

Directory rows mean all tracked files, preserving their relative suffixes.
Ignored caches, environments, archives, logs, and generated binaries are not
source files and are not moved into these destinations.

| Previous path | Canonical path |
| --- | --- |
| `Version 0_0_9/agent/` | `agent/` |
| `Version 0_0_9/tests/` | `tests/` |
| `Version 0_0_9/requirements.txt` | `requirements.txt` |
| `Version 0_0_9/deployment/Agent.spec` | `deployment/Agent.spec` |
| `Version 0_0_9/make_icon.py` | `deployment/make_icon.py` |
| `Version 0_0_9/docs/ARCHITECTURE.md` | `docs/ARCHITECTURE.md` |
| `Version 0_0_9/docs/CONFIGURATION.md` | `docs/CONFIGURATION.md` |
| `Version 0_0_9/docs/CONTRACTS.md` | `docs/CONTRACTS.md` |
| `Version 0_0_9/docs/ERROR_MODEL.md` | `docs/ERROR_MODEL.md` |
| `Version 0_0_9/docs/TEST_STRATEGY.md` | `docs/TEST_STRATEGY.md` |
| `Version 0_0_9/docs/TRANSPORT.md` | `docs/TRANSPORT.md` |
| `Version 0_0_9/docs/RELEASE_CHECKLIST.md` | `deployment/RELEASE_CHECKLIST.md` (generalized, unchecked) |
| `Version 0_0_9/pytest.ini` | pytest settings in `pyproject.toml` |
| active version README and root README | rewritten root `README.md` |
| version changelogs, release records, `docs/VERSION_HISTORY.md` | consolidated root `CHANGELOG.md` |

The active package and six test modules are unchanged. The package retains
`application/`, `composition.py`, and `agent.main.run`. The new root main.py
delegates to that function and preserves its exit code. Namespace package
discovery includes `application/ports` and `application/registry`.

The icon generator writes beside itself in deployment/. The PyInstaller spec
resolves the repository root from its own location. Both module execution
(`python -m agent`) and the root wrapper (`python main.py`) remain supported.

## Historical material and recovery

Version directories are removed from the current tree only after extracting
release facts and verifying that tracked contents exist in the baseline.
Ignored local material is preserved outside the repository before the directory
is removed. It must not be assumed to exist in Git merely because it is ignored.

All historical tracked files remain accessible, for example:

```powershell
git show '1a133e6c6ea1b02a039f45610182037d347390ba:Version 1_0_0/agent/core/worker.py'
git show '1a133e6c6ea1b02a039f45610182037d347390ba:Version 0_0_5/tests/test_dispatcher.py'
git show '1a133e6c6ea1b02a039f45610182037d347390ba:Version 0_0_9/docs/FINAL_AUDIT.md'
```

Commits and tags are not rewritten. The migration does not promote develop to
staging/main or create a release. Known behavioral, versioning, and historical
record discrepancies are listed individually in [KNOWN_ISSUES.md](KNOWN_ISSUES.md).

## Future work

Register and validate GitLab runners and the isolated smoke VM before retiring
the legacy workflow. Review older regression coverage separately. Any future
Kafka/Worker/Service integration requires a separate compatibility design;
copying historical files over the active package is not part of stage 1.
