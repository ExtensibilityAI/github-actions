# Pre-public hardening plan

Staff review of `github-actions` before flipping repository visibility to **public**.  
Current posture: solid WIF-first design, SHA-pinned third-party actions, BuildKit secrets, checksum-verified binaries. No secrets in-repo.

**Verdict:** Phase 1 and Phase 2 items below are implemented in `v2.1.0`. Configure org-level GitHub Environments (`release`, caller `prod`) before going public.

---

## Phase 1 — Blockers (before `visibility: public`)

| ID | Status | Issue | Action |
|----|--------|-------|--------|
| H1 | Done | `migration_extra_env` unsafe `$GITHUB_ENV` append | Key allowlist, newline rejection, `::add-mask::` |
| H2 | Done | Prod on any `push` | Gate prod on `main`/tags; feature branches → staging |
| H3 | Done | Unconstrained `dispatch_environment` | Whitelist `staging\|prod` |
| G1 | Done | No `LICENSE` | Apache-2.0 at repo root |
| G2 | Done | No `SECURITY.md` | Reporting process + caller WIF audit checklist |
| G3 | Done | Release workflow ungated | `environment: release` on `release.yml` |

---

## Phase 2 — High value (first month public)

| ID | Status | Issue | Action |
|----|--------|-------|--------|
| M1 | Done | Artifact name collision | SHA256 stem for `image-changed-*` artifacts |
| M2 | Done | `parse-image-matrix` weak validation | Paths, roles, `build_secret_env`, image name rules |
| M3 | Done | `ci-compose-config` word-split | Removed `compose_files` input; `docker compose config` only |
| M4 | Done | `detect-path-changes` regex grep | `grep -F` fixed-string |
| M5 | Done | `uv_index_prefix` interpolation | `^[A-Z][A-Z0-9_]{0,62}$` in setup-pypi/codeartifact |
| M6 | Done | WIF docs thin | README + SECURITY.md IAM example and audit checklist |
| M7 | Done | Blanket `secrets: inherit` | README documents minimal secret mappings |
| M10 | Done | `resolve-pulumi-org` shell interpolation | Inputs via `env:` |
| M11 | Done | actionlint skips composites | Workflow actionlint + composite metadata validation in CI |

---

## Phase 3 — Maturity (deferred)

- Second CODEOWNER / team review on shared library changes
- Fixture repo smoke-testing each reusable workflow on schedule
- Release automation that bumps internal `@vX.Y.Z` pins atomically
- Document recommended `on:` triggers per workflow (branch filters, no fork deploys)
- Caller template lint ensuring deploy workflows only trigger on `main`/tags

---

## v2.1.0 breaking changes (Pulumi)

- **Removed** unified `pulumi-deploy.yml` and `pulumi-destroy-app.yml` (no `cloud:` input).
- **Added** `pulumi-deploy-gcp.yml`, `pulumi-deploy-aws.yml`, `pulumi-destroy-app-gcp.yml`, `pulumi-destroy-app-aws.yml`.
- **Deploy order** is always **platform → apps** on both clouds. No `app_must_finish_first` / `lb_routes` / infra-ext-store app-first path.
- Callers must update workflow `uses:` paths and pin `@v2.1.0`.

---

## Public flip checklist

- [x] Phase 1 items merged and released (tag `v2.1.0`)
- [ ] All ExtensibilityAI callers pin `@v2.1.0` (not `@main`, not floating `@v2` in production)
- [ ] Org WIF pools audited for `attribute.repository` allowlists
- [ ] `prod` GitHub Environments have required reviewers on deploy workflows
- [ ] `release` GitHub Environment has required reviewers before tagging library releases
