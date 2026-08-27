# ExtensibilityAI GitHub Actions

Shared composite actions and reusable workflows for ExtensibilityAI platform apps, Python packages, and Pulumi infrastructure.

## Purpose

Centralize CI/CD patterns (GCP GKE/Helm deploy, package publish, Pulumi) so product repos stay thin callers that pin this library by version tag.

## Threat model

| Control | Rule |
| --- | --- |
| Visibility | This repository is **public code-only** (no secrets in the repo). |
| Pinning | Callers **must** pin with a release tag (`@v1.x.y`) or commit SHA — never `@main`. |
| Identity | GCP Workload Identity Federation must require `attribute.repository` (and prefer repo allowlists). |
| Secrets | No long-lived cloud keys in GitHub secrets for GCP; use WIF. Pulumi / GitHub App secrets stay in caller environments. |
| Third-party actions | Pin third-party actions to full commit SHAs with a `# vN` comment. |

## Supported surface

- **GCP GKE / Helm**: build & push Artifact Registry images, optional Cloud SQL migrations, kubectl or Helm rollout
- **Python packages**: CI (ruff/pytest) and publish to Artifact Registry PyPI
- **Pulumi**: path-filtered platform + app stack deploys (GCP and AWS), app-stack destroy

## Versioning

- Semver tags: `vMAJOR.MINOR.PATCH` (annotated)
- Moving major tag: `v1` points at the latest `v1.x.y`
- Callers: `ExtensibilityAI/github-actions/<action>@v1.0.0` or reusable workflow path `@v1.0.0`

Release via Actions → **Release** → `workflow_dispatch` with version input (from `main` or `trunk`).

## How to bump third-party action SHAs

1. Resolve the release tag on the upstream repo (e.g. `actions/checkout@v4`).
2. Replace every `uses:` pin with the full commit SHA and keep the `# vN` comment.
3. Update this README’s pin table if needed.
4. Cut a new library release (`v1.x.y`).

### Current pins

| Action | SHA comment |
| --- | --- |
| `actions/checkout` | `# v4` → `11d5960a326750d5838078e36cf38b85af677262` |
| `actions/setup-node` | `# v4` → `49933ea5288caeca8642d1e84afbd3f7d6820020` |
| `astral-sh/setup-uv` | `# v4` → `38f3f104447c67c051c4a08e39b64a148898af3a` |
| `google-github-actions/auth` | `# v2` → `c200f3691d83b41bf9bbd8638997a462592937ed` |
| `google-github-actions/setup-gcloud` | `# v2` → `e427ad8a34f8676edf47cf7d7925499adf3eb74f` |
| `google-github-actions/get-gke-credentials` | `# v2` → `64bc7249bbcf78056bb92f14d3cedc2da193946c` |
| `azure/setup-helm` | `# v4` → `1a275c3b69536ee54be43f2070a358922e12c8d4` |
| `actions/create-github-app-token` | `# v1` → `d72941d797fd3113feb6b93fd0dec494b13a2547` |
| `aws-actions/configure-aws-credentials` | `# v4` → `7474bc4690e29a8392af63c5b98e7449536d5c3a` |

Cloud SQL Auth Proxy: `v2.14.2` (checksum pinned in `install-cloud-sql-proxy`).  
actionlint: `1.7.12` (checksum pinned in `.github/workflows/actionlint.yml`).

## Composite actions

| Action | Description |
| --- | --- |
| `setup-pypi-auth` | WIF + export `UV_INDEX_*` for Artifact Registry PyPI |
| `setup-codeartifact-auth` | AWS OIDC + CodeArtifact token for uv |
| `resolve-github-token` | Mint GitHub App installation token as `GITHUB_TOKEN` |
| `resolve-pulumi-org` | `uv run infra utils resolve-pulumi-org` |
| `detect-changes` | `uv run infra utils detect-changes` (+ `app_must_finish_first`) |
| `install-cloud-sql-proxy` | Download + SHA256 verify proxy to `/usr/local/bin` |
| `set-deploy-env` | Resolve `env` / `stack` for app or package mode |
| `docker-build-push` | WIF build/push with `:latest` cache and change detection |

## Reusable workflows

| Workflow | Description |
| --- | --- |
| `ci-python-package.yml` | uv sync, ruff, pytest for a Python package |
| `publish-python-package.yml` | Version rewrite + twine to GAR PyPI |
| `ci-python-backend.yml` | Backend (± Postgres), optional frontend, light/compose_config styles |
| `deploy-gke-app.yml` | Build images, optional migrations/SDK publish, kubectl or Helm deploy |
| `pulumi-deploy.yml` | GCP/AWS path-filtered Pulumi platform + app stacks |
| `pulumi-destroy-app.yml` | Destroy per-slug app stacks |

## Caller examples

### Package CI + publish

```yaml
jobs:
  ci:
    uses: ExtensibilityAI/github-actions/.github/workflows/ci-python-package.yml@v1.0.0
    with:
      needs_pypi_auth: true
      uv_index_prefix: EXTENSIBILITY_AI
    secrets: inherit

  publish:
    needs: ci
    if: github.ref == 'refs/heads/main' || startsWith(github.ref, 'refs/tags/v')
    uses: ExtensibilityAI/github-actions/.github/workflows/publish-python-package.yml@v1.0.0
    with:
      uv_index_prefix: EXTENSIBILITY_AI
    secrets: inherit
```

### GKE app deploy

```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:
    inputs:
      environment:
        type: choice
        options: [prod, staging]

jobs:
  deploy:
    uses: ExtensibilityAI/github-actions/.github/workflows/deploy-gke-app.yml@v1.0.0
    with:
      api_image: lims-api
      api_dockerfile: backend/Dockerfile
      api_needs_pypi_auth: true
      frontend_image: lims-frontend
      frontend_context: frontend
      run_migrations: true
      db_secret_name_prefix: lims-db-password
      db_user: lims
      db_name: lims
      uv_index_prefix: EXTENSIBILITY_AI
    secrets: inherit
```

### Pulumi (GCP)

```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:
    inputs:
      environment: { type: choice, options: [staging, prod] }
      slug: { type: string, required: false }
      target: { type: choice, options: [app, platform, both], default: both }

jobs:
  deploy:
    uses: ExtensibilityAI/github-actions/.github/workflows/pulumi-deploy.yml@v1.0.0
    with:
      cloud: gcp
      platform_stack_name: infrastructure-core-gcp
      environment: ${{ github.event.inputs.environment || '' }}
      slug: ${{ github.event.inputs.slug || '' }}
      target: ${{ github.event.inputs.target || 'both' }}
    secrets: inherit
```

Nested composites inside this repo use relative paths (`./setup-pypi-auth`). Reusable workflows called from other repos reference composites as `ExtensibilityAI/github-actions/<name>@v1.0.0`.
