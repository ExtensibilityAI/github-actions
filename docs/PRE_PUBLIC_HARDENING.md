# Pre-public hardening plan

Staff review of `github-actions` before flipping repository visibility to **public**.  
Current posture: solid WIF-first design, SHA-pinned third-party actions, BuildKit secrets, checksum-verified binaries. No secrets in-repo.

**Verdict:** Conditionally ready — address Phase 1 blockers before going public.

---

## Phase 1 — Blockers (before `visibility: public`)

| ID | Severity | Issue | Action | Files |
|----|----------|-------|--------|-------|
| H1 | High | `migration_extra_env` lines appended to `$GITHUB_ENV` without key allowlist; values may be logged on parse failure | Parse with `^[A-Z][A-Z0-9_]{0,63}$` key regex; reject newlines; `::add-mask::` values; log line number only on failure | `cloud-sql-migrate/action.yml` |
| H2 | High | Prod environment selected on any `push`, not only `main`/tags | Gate prod on `refs/heads/main` or tag; default invalid dispatch env to staging | `set-deploy-env/action.yml`, `pulumi-deploy.yml` |
| H3 | High | `dispatch_environment` unconstrained — arbitrary GitHub Environment names | Whitelist `staging\|prod`; fail job otherwise | `set-deploy-env/action.yml` |
| G1 | Governance | No `LICENSE` | Add Apache-2.0 or MIT | repo root |
| G2 | Governance | No `SECURITY.md` | Add reporting process + caller WIF audit checklist | repo root |
| G3 | Governance | Release workflow has no approval gate; force-pushes moving `v2` | Protect release with GitHub Environment reviewers; document prefer exact semver pins over `@v2` | `release.yml`, org rulesets |

---

## Phase 2 — High value (first month public)

| ID | Severity | Issue | Action |
|----|----------|-------|--------|
| M1 | Medium | Artifact name sanitization collision in deploy matrix summary | Hash-based artifact stems; validate image names (no `/`) |
| M2 | Medium | `parse-image-matrix` lacks field validation | Validate paths (no `..`), `build_secret_env`, `role` enum |
| M3 | Medium | `ci-compose-config` shell word-splits `compose_files` | Fixed file list or JSON array parsed without shell |
| M4 | Medium | `detect-path-changes` uses regex grep on prefix | Use `grep -F` fixed-string |
| M5 | Medium | `uv_index_prefix` not validated before env var interpolation | `^[A-Z][A-Z0-9_]{0,62}$` |
| M6 | Medium | WIF enforcement documented but not verifiable in-repo | Expand README with IAM condition JSON; caller audit checklist |
| M7 | Medium | README encourages blanket `secrets: inherit` | Document minimal secret mappings per workflow |
| M10 | Medium | `resolve-pulumi-org` interpolates inputs in shell | Pass via `env:` + quoted expansion |
| M11 | Medium | actionlint skips composite `action.yml` | Lint `**/action.yml` in CI |

---

## Phase 3 — Maturity

- Second CODEOWNER / team review on shared library changes
- Fixture repo smoke-testing each reusable workflow on schedule
- Release automation that bumps internal `@vX.Y.Z` pins atomically
- Document recommended `on:` triggers per workflow (branch filters, no fork deploys)
- Caller template lint ensuring deploy workflows only trigger on `main`/tags

---

## Threat model gaps to close in README

| Topic | Status | Required addition |
|-------|--------|-------------------|
| WIF `attribute.repository` binding | Aspirational | Example IAM condition + audit steps |
| Branch filters for prod deploy | Missing | Callers must use `on.push.branches: [main]` |
| GitHub Environment protection | Missing | Required reviewers for `prod` |
| Fork PR / `pull_request_target` | Missing | Never run privileged deploys from untrusted forks |
| `secrets: inherit` scope | Partial | Prefer explicit mappings for CI-only jobs |
| Moving major tag semantics | Missing | `@v2` is force-updated; pin exact patch versions |
| `migration_extra_env` injection | Partial | Document secret wire-through; never log values |

---

## Positive controls (keep)

- Third-party actions pinned to full commit SHA with `# vN` comments
- Docker BuildKit `--secret id=...,env=VAR` (not build-args)
- `kubectl-rollout` uses subprocess list form (injection-safe)
- Cloud SQL proxy download: version + SHA256 checksum
- `resolve-github-token` masks token before `$GITHUB_ENV`
- Build-summary artifacts: 1-day retention, boolean flags only
- App-agnostic reusable surface (no product-specific secret names in library code)

---

## Public flip checklist

- [ ] Phase 1 items merged and released (tag `v2.x.y`)
- [ ] All ExtensibilityAI callers pin `@v2.x.y` (not `@main`, not floating `@v2` in production)
- [ ] Org WIF pools audited for `attribute.repository` allowlists
- [ ] `prod` GitHub Environments have required reviewers on deploy workflows
- [ ] LICENSE + SECURITY.md published
- [ ] Branch protection on `trunk`/`main` (reviews, no force-push)
- [ ] Release workflow restricted to maintainers
