# ExtensibilityAI GitHub Actions

Shared composite actions and reusable workflows for ExtensibilityAI platform apps, Python packages, and Pulumi infrastructure.

## Purpose

Centralize CI/CD patterns (GCP GKE/Helm deploy, package publish, Pulumi) so product repos stay thin callers that pin this library by version tag.

## Threat model

| Control | Rule |
| --- | --- |
| Visibility | Intended **public code-only** once the hardening bar passes (currently private; org Actions access enabled for ExtensibilityAI callers). No secrets in the repo. |
| Pinning | Callers **must** pin with a release tag (`@v2.x.y`) or commit SHA — never `@main` / `@trunk`. |
| Identity | GCP Workload Identity Federation must require `attribute.repository` (and prefer repo allowlists). |
| Secrets | No long-lived cloud keys in GitHub secrets for GCP; use WIF. Pulumi / GitHub App secrets stay in caller environments. |
| App-agnostic | Reusable workflows/actions must **never** reference product-specific `vars.*` / `secrets.*` names (e.g. `SCAFFOLDER_*`). Callers may pass opaque `KEY=VALUE` blobs via the `migration_extra_env` **secret** (not a `with:` input — GitHub forbids `secrets.*` in reusable workflow inputs). |
| Third-party actions | Pin third-party actions to full commit SHAs with a `# vN` comment. |

## Supported surface

- **GCP GKE / Helm**: JSON image matrix build & push, optional Cloud SQL migrations, kubectl or Helm rollout
- **Python packages**: CI (blocking ruff + pytest) and publish to Artifact Registry PyPI
- **Python backends**: CI with Postgres; light import CI; compose-config CI
- **Pulumi**: path-filtered platform + app stack deploys (GCP and AWS), app-stack destroy

## Versioning

- Semver tags: `vMAJOR.MINOR.PATCH` (annotated)
- Moving major tag: `v2` points at the latest `v2.x.y`
- Callers: `ExtensibilityAI/github-actions/<action>@v2.0.0` or reusable workflow path `@v2.0.0`

Release via Actions → **Release** → `workflow_dispatch` with version input (from `main` or `trunk`).

## How to bump third-party action SHAs

1. Resolve the release tag on the upstream repo (e.g. `actions/checkout@v4`).
2. Replace every `uses:` pin with the full commit SHA and keep the `# vN` comment.
3. Update this README’s pin table if needed.
4. Cut a new library release (`v2.x.y`).

### Current pins

| Action | SHA comment |
| --- | --- |
| `actions/checkout` | `# v4` → `11d5960a326750d5838078e36cf38b85af677262` |
| `actions/setup-node` | `# v4` → `49933ea5288caeca8642d1e84afbd3f7d6820020` |
| `actions/upload-artifact` | `# v4` → `ea165f8d65b6e75b540449e92b4886f43607fa02` |
| `actions/download-artifact` | `# v4` → `d3f86a106a0bac45b974a628896c90dbdf5c8093` |
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
| `detect-path-changes` | Git diff whether a directory prefix changed |
| `parse-image-matrix` | Normalize JSON image list for deploy matrix |
| `install-cloud-sql-proxy` | Download + SHA256 verify proxy to `/usr/local/bin` |
| `set-deploy-env` | Resolve `env` / `stack`: PR→staging, push/tag→prod, dispatch→input |
| `docker-build-push` | WIF build/push with `:latest` cache and change detection |
| `cloud-sql-migrate` | Secret Manager + proxy + alembic (opaque `extra_env` allowed) |
| `publish-python-sdk` | Version rewrite + twine for an SDK package directory |
| `kubectl-rollout` | SHA-based kubectl set image for changed images |
| `helm-rollout` | SHA-based helm upgrade --reuse-values |

**CI vs deploy environments:** Package/app **CI** workflows use a GitHub Environment (default `staging`) only to load WIF vars for private PyPI during tests — they do not deploy. **Deploy/publish** workflows call `set-deploy-env` so pushes to `main` and tags use `prod`, while pull requests use `staging`.

## Reusable workflows

| Workflow | Description |
| --- | --- |
| `ci-python-package.yml` | uv sync, **blocking** ruff, pytest for a Python package |
| `publish-python-package.yml` | Version rewrite + twine to GAR PyPI |
| `ci-python-backend.yml` | Backend + Postgres, blocking ruff, pytest; optional frontend job |
| `ci-python-light.yml` | Lightweight uv sync / import or pytest (no private index) |
| `ci-compose-config.yml` | bash -n scripts + `docker compose config` |
| `deploy-gke-app.yml` | Image matrix build, optional migrations/SDK, kubectl or Helm |
| `pulumi-deploy.yml` | GCP/AWS path-filtered Pulumi platform + app stacks |
| `pulumi-destroy-app.yml` | Destroy per-slug app stacks |

## Caller examples

**Required:** jobs that `uses:` a reusable workflow must declare any permissions nested jobs need (at least `id-token: write` and `contents: read` for WIF).

### Package CI + publish

```yaml
jobs:
  ci:
    permissions:
      id-token: write
      contents: read
    uses: ExtensibilityAI/github-actions/.github/workflows/ci-python-package.yml@v2.0.0
    with:
      needs_pypi_auth: true
      uv_index_prefix: EXTENSIBILITY_AI
      github_environment: staging
    secrets: inherit

  publish:
    permissions:
      id-token: write
      contents: read
    uses: ExtensibilityAI/github-actions/.github/workflows/publish-python-package.yml@v2.0.0
    with:
      uv_index_prefix: EXTENSIBILITY_AI
    secrets: inherit
```

### GKE app deploy

```yaml
jobs:
  deploy:
    permissions:
      id-token: write
      contents: read
    uses: ExtensibilityAI/github-actions/.github/workflows/deploy-gke-app.yml@v2.0.0
    with:
      images: |
        [{"name":"lims-api","dockerfile":"backend/Dockerfile","needs_pypi_auth":true,"build_secret_env":"UV_INDEX_EXTENSIBILITY_AI_PYPI_PASSWORD","role":"api"},
         {"name":"lims-frontend","dockerfile":"frontend/Dockerfile","context":"frontend","role":"frontend"}]
      run_migrations: true
      db_secret_name_prefix: lims-db-password
      db_user: lims
      db_name: lims
      uv_index_prefix: EXTENSIBILITY_AI
      dispatch_environment: ${{ github.event_name == 'workflow_dispatch' && github.event.inputs.environment || '' }}
    secrets: inherit
```

Product-specific migrate env (scaffolder only) belongs in the **caller** as a
`secrets:` mapping (cannot use `secrets: inherit` in the same job when passing an
explicit secret). Vars may be interpolated into the secret value:

```yaml
    secrets:
      migration_extra_env: |
        SCAFFOLDER_GITHUB_ORG=${{ vars.SCAFFOLDER_GITHUB_ORG }}
        SCAFFOLDER_GITHUB_APP_PRIVATE_KEY_PEM=${{ secrets.SCAFFOLDER_GITHUB_APP_PRIVATE_KEY_PEM }}
```

Callers that do not need extra migrate env keep `secrets: inherit`.

### Pulumi (GCP)

```yaml
jobs:
  deploy:
    permissions:
      id-token: write
      contents: read
    uses: ExtensibilityAI/github-actions/.github/workflows/pulumi-deploy.yml@v2.0.2
    with:
      cloud: gcp
      # platform_stack_name defaults to infrastructure-core-gcp; override for store repos
      environment: ${{ github.event_name == 'workflow_dispatch' && github.event.inputs.environment || '' }}
      slug: ${{ github.event_name == 'workflow_dispatch' && github.event.inputs.slug || '' }}
      target: ${{ github.event_name == 'workflow_dispatch' && github.event.inputs.target || 'both' }}
    secrets: inherit
```

### Pulumi (AWS)

```yaml
jobs:
  deploy:
    permissions:
      id-token: write
      contents: read
    uses: ExtensibilityAI/github-actions/.github/workflows/pulumi-deploy.yml@v2.0.2
    with:
      cloud: aws
      environment: ${{ github.event_name == 'workflow_dispatch' && github.event.inputs.environment || '' }}
      slug: ${{ github.event_name == 'workflow_dispatch' && github.event.inputs.slug || '' }}
      target: ${{ github.event_name == 'workflow_dispatch' && github.event.inputs.target || 'both' }}
    secrets: inherit
```

### Pulumi destroy app

```yaml
jobs:
  destroy:
    permissions:
      id-token: write
      contents: read
    uses: ExtensibilityAI/github-actions/.github/workflows/pulumi-destroy-app.yml@v2.0.2
    with:
      cloud: gcp  # or aws
      slug: ${{ github.event.inputs.slug }}
      environments: ${{ github.event.inputs.environments }}
    secrets: inherit
```

**Required caller secrets:** `PULUMI_ACCESS_TOKEN`, `INFRA_GITHUB_TOKEN`, `INFRA_GITHUB_APP_ID`, `INFRA_GITHUB_APP_PRIVATE_KEY`

**GCP vars:** `WIF_PROVIDER`, `GCP_SA`, `GCP_PROJECT_ID`, `GCP_REGION` (as used by your stacks)

**AWS vars:** `AWS_ROLE_ARN`, `AWS_REGION`, `CODEARTIFACT_DOMAIN` (for CodeArtifact auth)

Composite actions that nest other composites **must** use fully-qualified `ExtensibilityAI/github-actions/<name>@vX.Y.Z` pins. Relative `./` paths resolve in the *caller* workspace and break cross-repo.
