# Release checklist

## Work Item #15 update trust policy

An update candidate must have a trusted signer identity and exact SHA-256 integrity
match before staging. It becomes last-known-good only after a health gate. This repository
does not download, execute, or roll back an updater; package signing, rollout and end-to-end
rollback remain **PENDING PRODUCTION VALIDATION**.

Start a fresh unchecked checklist for every candidate. This template is not a
record of a completed release. Historical release facts are in ../CHANGELOG.md.

## Candidate and source

- [ ] Record the candidate commit, intended version, and approved scope.
- [ ] Confirm GitLab is the source of truth and GitHub is downstream only.
- [ ] Confirm the candidate retains the approved development ancestry.
- [ ] Review CHANGELOG.md and resolve or explicitly accept known issues.
- [ ] Reconcile package, runtime identity, and executable versions before release.
- [ ] Confirm no secrets, local environments, caches, or build outputs are tracked.

## Validation

- [ ] GitLab CI Lint accepts .gitlab-ci.yml for the installed GitLab version.
- [ ] Verify registered local Windows runner tags and no-MT5 isolation.
- [ ] Validate active source syntax, imports, and package discovery.
- [ ] Run pytest from repository root; collection is confined to tests/.
- [ ] Generate the icon with python deployment/make_icon.py.
- [ ] Build with python -m PyInstaller deployment/Agent.spec --clean --noconfirm.
- [ ] Verify dist/MT5Agent-v0.1.2.exe exists and matches the canonical source version.
- [ ] Verify invalid startup configuration exits with code 2.
- [ ] On an isolated VM without an accessible MT5 terminal, verify exit code 1.
- [ ] Record manual Windows/MT5 graceful-shutdown acceptance for the candidate.
- [ ] Complete all GitLab stages, including the blocking manual smoke job.
- [ ] Verify the packaged executable is byte-identical to the smoke-tested file.
- [ ] Record its SHA-256 and verify the downloaded final CI artifact.

## Authorized promotion and release

- [ ] Obtain approval for promotion from develop to staging, then to main.
- [ ] Obtain separate approval before creating a new tag or release.
- [ ] Preserve every existing tag and published release unchanged.
- [ ] Publish the exact verified binary and checksum, without rebuilding it.
- [ ] Verify downstream mirroring; do not commit or merge directly on GitHub.
- [ ] Confirm GitHub remains mirror/archive only with no Actions workflow.
