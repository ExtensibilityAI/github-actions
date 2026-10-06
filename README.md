# ExtensibilityAI GitHub Actions

Shared composite actions and reusable workflows for ExtensibilityAI platform apps, Python packages, and Pulumi infrastructure.

## Purpose

Centralize CI/CD patterns (GCP GKE/Helm and AWS EKS/Helm deploy, package publish, Pulumi) so product repos stay thin callers that pin this library by version tag.

## Threat model

| Control | Rule |
| --- | --- |
| Visibility | Intended **public code-only** once the hardening bar passes (currently private; org Actions access enabled for ExtensibilityAI callers). No secrets in the repo. |
| Pinning | Callers **must** pin with a release tag (`@v2.x.y`) or commit SHA — never `@main` / `@trunk`. |
| Identity | GCP Workload Identity Federation must require `attribute.repository` (and prefer repo allowlists). See [SECURITY.md](SECURITY.md) for an IAM condition example and caller audit checklist. |
| Branch filters | Deploy callers must trigger production only from `main` or release tags (`on.push.branches: [main]`). PRs resolve to `staging` via `set-deploy-env`. |
| Environments | Configure GitHub Environment protection on `prod` (required reviewers). The library `release` workflow uses the `release` environment for tag pushes. |
| Secrets | No long-lived cloud keys in GitHub secrets for GCP; use WIF. Pulumi callers **must** pass `INFRA_GITHUB_APP_ID` / `INFRA_GITHUB_APP_PRIVATE_KEY` explicitly — `secrets: inherit` only works in the same GitHub organization or enterprise, so customer orgs (e.g. ExtensibilityStore) calling this library get empty App credentials. Pulumi DIY backends use environment variable `PULUMI_BACKEND_URL` (`gs://…` or `s3://…`). |
| App-agnostic | Reusable workflows/actions must **never** reference product-specific `vars.*` / `secrets.*` names (e.g. `SCAFFOLDER_*`). Callers may pass opaque `KEY=VALUE` blobs via the `migration_extra_env` **secret** (not a `with:` input — GitHub forbids `secrets.*` in reusable workflow inputs). Multiline values (PEMs) are supported: lines after `KEY=` continue until the next allowlisted `KEY=` assignment. |
| Third-party actions | Pin third-party actions to full commit SHAs with a `# vN` comment. |

## Supported surface

- **GCP GKE / Helm**: JSON image matrix build & push, optional in-cluster migrate Job (`k8s-migrate`), Helm rollout
- **AWS EKS / Helm**: JSON image matrix build & push to ECR, optional in-cluster migrate Job (`k8s-migrate` / `rds-migrate` wrapper) + CodeArtifact SDK publish, Helm rollout (`deploy-eks-app.yml`)
- **Python packages**: CI (blocking ruff + pytest) and publish to Artifact Registry PyPI or AWS CodeArtifact (`cloud: gcp|aws`)
- **Python backends**: CI with Postgres; light import CI; compose-config CI
- **Pulumi**: path-filtered platform + app stack deploys (GCP and AWS), app-stack destroy; per-stack `uv sync` in stack workdirs plus root CLI sync
- **Renovate**: self-hosted infra dependency updates (`renovate-infra-deps.yml`) with caller-owned `renovate.json`; auth via Infra GitHub App (`INFRA_GITHUB_APP_*`), same as Pulumi deploy — no dedicated `RENOVATE_TOKEN`

## Versioning

- Semver tags: `vMAJOR.MINOR.PATCH` (annotated)
- Moving major tag: `v2` points at the latest `v2.x.y`
- Callers: `ExtensibilityAI/github-actions/<action>@v2.9.3` or reusable workflow path `@v2.9.3` (`k8s-migrate` / `rds-migrate` connect directly to the database when ConfigMap `app-env` has `DATABASE_DIRECT_HOST`, which an app behind a PgBouncer pooler has; GKE migrations use the same in-cluster Job path via `k8s-migrate` instead of runner-side `cloud-sql-migrate`; `helm-rollout` pins Helm v4.3.0 and upgrades with `--server-side=false`, so a Deployment KEDA has scaled away from the chart's `replicas` no longer fails with a server-side-apply conflict; with `values_files`, `helm-rollout` drops a removed worker's `workers.<name>` from the release: it upgrades with `--reset-values` from the pruned previous values instead of `--reuse-values`; `images_file` and `values_files` take comma-separated lists and globs, e.g. `workers/*/deploy/image.json`, and duplicate image names fail; `values_files` input on deploy-gke-app / deploy-eks-app; per-image `values_key` and `images_file` on deploy-gke-app / deploy-eks-app; `helm-rollout` prefixes a bare `ARTIFACTS_BUCKET` with `s3://` when `cloud: aws`, otherwise `gs://`; EKS `rds-migrate` default `alembic upgrade head` for TAG images with `PATH` + `PYTHONPATH`, not `uv run`; `cloud: aws` on python CI/publish; CodeArtifact twine URL `/pypi/{repo}/`; `CODEARTIFACT_DOMAIN_OWNER` + fail-closed app-stack auth; required `uv_index_prefix`; multiline `migration_extra_env`; Helm-native deploy; DIY secrets sync for GCS **and** S3; AWS `drop-assume-role` via root `infra` CLI). Older pins: `@v2.9.3` and earlier use `cloud-sql-migrate` (runner + public Cloud SQL IP) on GKE; `@v2.9.2` migrates through `app-env`'s `DATABASE_HOST` even behind a pooler; `@v2.9.1` (its deploy workflows still call `helm-rollout@v2.9.0`), `@v2.9.0` and earlier install the latest Helm and use its default apply mode (server-side on Helm 4); `@v2.8.0` keeps a removed worker's values (and so its workload) under `--reuse-values`; `@v2.7.0` takes a single `images_file` path and no `values_files` on the deploy workflows; `@v2.6.11` has no `values_key` / `images_file`; `@v2.6.10` still prefixes bare `ARTIFACTS_BUCKET` with `gs://`; `@v2.6.8` still uses `uv run alembic` in the migrate Job; `@v2.6.7` for CodeArtifact domain-owner without python `cloud`; `@v2.6.6` for assume-role CLI without domain-owner; `@v2.6.5` for S3 DIY sync without the assume-role CLI fix; `@v2.6.0`–`@v2.6.4` for Helm-native without S3 sync; `@v2.5.0` for Helm-native without required prefix; `@v2.4.0` for Helm-only without multiline migrate. **Pulumi DIY backends** require GitHub environment variable `PULUMI_BACKEND_URL` (`gs://…` or `s3://…`).
- **`uv_index_prefix` is required** on reusable workflows that authenticate to a private uv index (no default). Pass the deployment-specific prefix that matches `[[tool.uv.index]]` (hyphens→underscores, without trailing `_PYPI`), e.g. `EXT_STORE_INFRA_3320` for index `ext-store-infra-3320-pypi`.

Release via Actions → **Release** → `workflow_dispatch` with version input (from `main` or `trunk`). The job runs in the GitHub Environment **`release`** — configure required reviewers on that environment before cutting tags.

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
| `aws-actions/amazon-ecr-login` | `# v2` → `03f1aad4c6c7ffd436567f42f9384779290529bd` |

Cloud SQL Auth Proxy: `v2.14.2` (checksum pinned in `install-cloud-sql-proxy`; deprecated with `cloud-sql-migrate` — prefer `k8s-migrate`).  
actionlint: `1.7.12` (checksum pinned in `.github/workflows/actionlint.yml`). Local mirror: `pre-commit install` then `pre-commit run --all-files` (see `.pre-commit-config.yaml`).

## Composite actions

| Action | Description |
| --- | --- |
| `setup-pypi-auth` | WIF + export `UV_INDEX_*` for Artifact Registry PyPI |
| `setup-codeartifact-auth` | AWS OIDC + CodeArtifact token for uv (`codeartifact_domain_owner`; `required` fails closed) |
| `resolve-github-token` | Mint GitHub App installation token as `GITHUB_ACCESS_TOKEN` / `GH_TOKEN` (do not overwrite reserved `GITHUB_TOKEN`) |
| `resolve-pulumi-org` | `uv run infra utils resolve-pulumi-org` |
| `detect-changes` | `uv run infra utils detect-changes` (platform → apps deploy order) |
| `detect-path-changes` | Git diff whether a directory prefix changed |
| `parse-image-matrix` | Normalize JSON image list for deploy matrix |
| `install-cloud-sql-proxy` | **Deprecated** — only used by `cloud-sql-migrate`. Prefer `k8s-migrate`. Download + SHA256 verify proxy to `/usr/local/bin` |
| `set-deploy-env` | Resolve `env` / `stack`: PR→staging, push/tag→prod, dispatch→input |
| `docker-build-push` | WIF build/push with `:latest` cache and change detection (GAR) |
| `docker-build-push-aws` | OIDC + ECR login, build/push with `:latest` cache and change detection |
| `k8s-migrate` | In-cluster Job alembic (`cloud: gcp\|aws`); ConfigMap `app-env` + Secret `db`; prefers `DATABASE_DIRECT_HOST`/`PORT` when set (pooler-safe), else `DATABASE_HOST`/`PORT` |
| `cloud-sql-migrate` | **Deprecated** — use `k8s-migrate` (`cloud: gcp`). Runner-side Secret Manager + Cloud SQL Auth Proxy + alembic (needs public IP) |
| `rds-migrate` | Thin wrapper around `k8s-migrate` with `cloud: aws` (same Job / `DATABASE_DIRECT_*` behaviour) |
| `publish-python-sdk` | Version rewrite + twine to Artifact Registry PyPI |
| `publish-python-sdk-aws` | Version rewrite + twine to CodeArtifact PyPI |
| `helm-rollout` | SHA-based helm upgrade --reuse-values (Helm v4.3.0, client-side apply so KEDA/HPA-scaled replicas do not conflict) |
| `sync-diy-stack-secrets` | Rehydrate `secretsprovider`/`encryptedkey` from GCS or S3 DIY checkpoint into `Pulumi.<stack>.yaml` |

### Pulumi GitHub token

`resolve-github-token` mints a GitHub App installation token and exports it as **`GITHUB_ACCESS_TOKEN`** and **`GH_TOKEN`**, plus step **`outputs.token`**.

- **Never** write reserved **`GITHUB_TOKEN`** to `$GITHUB_ENV`. GitHub ignores that overwrite in reusable workflows, so later steps keep the default Actions token (scoped to the caller repo) and 401 on other-repo environment APIs.
- Pulumi destroy steps overlay `GITHUB_ACCESS_TOKEN` and `GH_TOKEN` from `steps.github-token.outputs.token`.
- Python preflight then **overwrites** process `GITHUB_TOKEN` / `GH_TOKEN` from `GITHUB_ACCESS_TOKEN`. Destroy uses `pulumi destroy --run-program` so providers re-read the live App token (~1h) instead of the value stored in Pulumi state.

**CI vs deploy environments:** Package/app **CI** workflows use a GitHub Environment (default `staging`) only to load WIF vars for private PyPI during tests — they do not deploy. **Deploy/publish** workflows call `set-deploy-env` so pushes to `main` and tags use `prod`, while pull requests use `staging`.

## Reusable workflows

| Workflow | Description |
| --- | --- |
| `ci-python-package.yml` | uv sync, **blocking** ruff, pytest; `cloud: gcp` (default) or `aws` |
| `publish-python-package.yml` | Version rewrite + twine to GAR PyPI or CodeArtifact (`cloud: gcp|aws`) |
| `ci-python-backend.yml` | Backend + Postgres, blocking ruff, pytest; optional frontend job; `cloud: gcp|aws` |
| `ci-python-light.yml` | Lightweight uv sync / import or pytest (no private index) |
| `ci-compose-config.yml` | bash -n scripts + `docker compose config` |
| `deploy-gke-app.yml` | Image matrix build, optional in-cluster migrate Job / SDK, Helm rollout (GCP; Helm-only) |
| `deploy-eks-app.yml` | Image matrix build to ECR, optional in-cluster migrate Job / CodeArtifact SDK, Helm rollout (AWS; Helm-only) |
| `pulumi-deploy-gcp.yml` | GCP path-filtered Pulumi: platform stack, then app stacks (root CLI `uv sync` + per-stack `uv sync`) |
| `pulumi-deploy-aws.yml` | AWS path-filtered Pulumi: platform stack, then app stacks (same dual-sync pattern) |
| `pulumi-destroy-app-gcp.yml` | Destroy one GCP app stack (`slug` + `environment`) via `infra app-destroy` (helm uninstall then `pulumi destroy`) |
| `pulumi-destroy-app-aws.yml` | Destroy one AWS app stack (`slug` + `environment`) via `infra app-destroy` (helm uninstall then `pulumi destroy`) |
| `renovate-infra-deps.yml` | Self-hosted Renovate with GAR/CodeArtifact auth; uses Infra GitHub App token (same as deploy); policy from caller `renovate.json` |

## Caller examples

**Required:** jobs that `uses:` a reusable workflow must declare any permissions nested jobs need (at least `id-token: write` and `contents: read` for WIF).

### Package CI + publish

```yaml
jobs:
  ci:
    permissions:
      id-token: write
      contents: read
    uses: ExtensibilityAI/github-actions/.github/workflows/ci-python-package.yml@v2.6.8
    with:
      needs_pypi_auth: true
      uv_index_prefix: EXTENSIBILITY_AI
      github_environment: staging
      cloud: gcp
    secrets: inherit

  publish:
    permissions:
      id-token: write
      contents: read
    uses: ExtensibilityAI/github-actions/.github/workflows/publish-python-package.yml@v2.6.8
    with:
      uv_index_prefix: EXTENSIBILITY_AI
      cloud: gcp
    secrets: inherit
```

### GKE app deploy

```yaml
jobs:
  deploy:
    permissions:
      id-token: write
      contents: read
    uses: ExtensibilityAI/github-actions/.github/workflows/deploy-gke-app.yml@v2.6.0
    with:
      images: |
        [{"name":"lims-api","dockerfile":"backend/Dockerfile","needs_pypi_auth":true,"build_secret_env":"UV_INDEX_EXTENSIBILITY_AI_PYPI_PASSWORD","role":"api"},
         {"name":"lims-frontend","dockerfile":"frontend/Dockerfile","context":"frontend","role":"frontend"}]
      # role is a Kubernetes DNS label matching cloud.services[].name (api, frontend, or a custom name).
      helm_chart: ./chart
      run_migrations: true
      # Optional: migration_image_name / migration_service_account (defaults: first image / api)
      uv_index_prefix: EXTENSIBILITY_AI
      dispatch_environment: ${{ github.event_name == 'workflow_dispatch' && github.event.inputs.environment || '' }}
    secrets: inherit
```

Deploy is **Helm-only** (no `deploy_method` / kubectl). Pass `helm_chart` (local `./chart` or upstream).

**Migrations** run as an in-cluster Kubernetes Job (`k8s-migrate` with `cloud: gcp`) using the just-built image, ConfigMap `app-env`, and Secret `db` (created by the app Pulumi stack). Prefer this over the deprecated `cloud-sql-migrate` (runner + Cloud SQL Auth Proxy), which needs a public IP.

When `cloud.db.pooler` is enabled, `app-env` sets `DATABASE_HOST`/`DATABASE_PORT` to PgBouncer and `DATABASE_DIRECT_HOST`/`DATABASE_DIRECT_PORT` to the database. `k8s-migrate` prefers `DATABASE_DIRECT_*` when present so alembic bypasses the pooler; otherwise it uses `DATABASE_HOST`/`PORT` from `envFrom`.

Inputs `db_secret_name_prefix`, `db_user`, `db_name`, and `instance_name_prefix` are **ignored** (kept so older callers do not fail validation). Pass `migration_image_name` (defaults to the first matrix image) and `migration_service_account` (default `api`) instead.

**Image values keys.** `helm-rollout` takes each image's chart key from the image name's
last `-` segment (`<slug>-api` → `services.api.image.*`, `<slug>-worker` →
`worker.image.*`). To target any other key, set `values_key` on the image, e.g.
`{"name":"lims-worker-billing","dockerfile":"workers/billing/Dockerfile","values_key":"workers.billing","role":"worker-billing"}`
sets `workers.billing.image.repository` / `.tag` (from `@v2.7.0`).

**Image list in a file.** Instead of `images`, pass `images_file: .github/images.json`
(a JSON file with the same array) so tools can edit the list as plain JSON (from `@v2.7.0`).

**Workers found by glob.** `images_file` and `values_files` take comma-separated paths
and globs (from `@v2.8.0`), so a project picks up self-contained worker directories
without editing a shared file:

```yaml
      images_file: .github/images.json,workers/*/deploy/image.json
      values_files: chart/values.yaml,workers/*/deploy/values.yaml
```

Arrays and values files are used in list order, each glob's matches sorted; a glob that
matches nothing is fine. Image names must be unique across all files.

**Removing a worker.** With `values_files`, an upgrade of an existing release removes
each `workers.<name>` that is in the release's values but in no values file, so deleting
`workers/<name>/` removes the worker's workload on the next deploy (from `@v2.9.0`).
Everything else in the previous values, such as the image tags of images the deploy did
not rebuild, is carried over as under `--reuse-values`.

Product-specific migrate env (scaffolder only) belongs in the **caller** as a
`secrets:` mapping (cannot use `secrets: inherit` in the same job when passing an
explicit secret). Vars may be interpolated into the secret value. Multiline
secrets (PEMs) may span lines after `KEY=`; `k8s-migrate` / `rds-migrate`
(and deprecated `cloud-sql-migrate`) write them via GITHUB_ENV heredocs or JSON
Job env:

```yaml
    secrets:
      migration_extra_env: |
        SCAFFOLDER_GITHUB_ORG=${{ vars.SCAFFOLDER_GITHUB_ORG }}
        SCAFFOLDER_GITHUB_APP_PRIVATE_KEY_PEM=${{ secrets.SCAFFOLDER_GITHUB_APP_PRIVATE_KEY_PEM }}
```

Callers that do not need extra migrate env keep `secrets: inherit`.

### EKS app deploy

```yaml
jobs:
  deploy:
    permissions:
      id-token: write
      contents: read
    uses: ExtensibilityAI/github-actions/.github/workflows/deploy-eks-app.yml@v2.6.0
    with:
      images: |
        [{"name":"lims-api","dockerfile":"backend/Dockerfile","needs_pypi_auth":true,"build_secret_env":"UV_INDEX_ACCOUNT_PYPI_PASSWORD","role":"api"}]
      helm_chart: ./chart
      run_migrations: true
      publish_sdk: false
      uv_index_prefix: ACCOUNT
      dispatch_environment: ${{ github.event_name == 'workflow_dispatch' && github.event.inputs.environment || '' }}
    secrets: inherit
```

**Migrations** run as an EKS Job (`k8s-migrate` with `cloud: aws`, or the `rds-migrate` wrapper) using the just-built image, ConfigMap `app-env`, and Secret `db` (created by the app Pulumi stack). GitHub-hosted runners cannot reach VPC-private RDS directly. The default Job command is `alembic upgrade head` (image `PATH` must include `.venv/bin` and `PYTHONPATH` must include the app). Override `migration_command` if needed; do not use `uv run` on `--no-install-project` images (it tries to write `*.egg-info` as a non-root user).

When `app-env` has `DATABASE_DIRECT_HOST` (PgBouncer pooler), the Job overrides `DATABASE_HOST`/`DATABASE_PORT` from `DATABASE_DIRECT_*` so migrations hit the database, not the pooler.

**SDK publish** uses `publish-python-sdk-aws` → CodeArtifact. Ensure `infra-gh` (or `codeartifact.publisherPrincipals`) can `PublishPackageVersion`.

Requires environment vars from the app/platform Pulumi sync: `AWS_ROLE_ARN`, `AWS_REGION`, `AWS_ACCOUNT_ID`, `EKS_CLUSTER_NAME`, `K8S_NAMESPACE`, `HELM_RELEASE` (optional `IMAGE_REGISTRY`, `EKS_REGION`; CodeArtifact: `CODEARTIFACT_DOMAIN`, `CODEARTIFACT_DOMAIN_OWNER`, optional `CODEARTIFACT_REPOSITORY`).

### Pulumi (GCP)

```yaml
jobs:
  deploy:
    permissions:
      id-token: write
      contents: read
    uses: ExtensibilityAI/github-actions/.github/workflows/pulumi-deploy-gcp.yml@v2.6.0
    with:
      uv_index_prefix: EXT_STORE_INFRA_3320  # must match [[tool.uv.index]] name
      environment: ${{ github.event_name == 'workflow_dispatch' && github.event.inputs.environment || '' }}
      slug: ${{ github.event_name == 'workflow_dispatch' && github.event.inputs.slug || '' }}
      target: ${{ github.event_name == 'workflow_dispatch' && github.event.inputs.target || 'both' }}
    secrets:
      INFRA_GITHUB_APP_ID: ${{ secrets.INFRA_GITHUB_APP_ID }}
      INFRA_GITHUB_APP_PRIVATE_KEY: ${{ secrets.INFRA_GITHUB_APP_PRIVATE_KEY }}
      INFRA_GITHUB_TOKEN: ${{ secrets.INFRA_GITHUB_TOKEN }}
```

`secrets: inherit` is **not** sufficient when the caller lives in a different GitHub organization than this library (customer infra-core repos). Named `workflow_call` secrets must be passed explicitly.

### Pulumi (AWS)

```yaml
jobs:
  deploy:
    permissions:
      id-token: write
      contents: read
    uses: ExtensibilityAI/github-actions/.github/workflows/pulumi-deploy-aws.yml@v2.6.0
    with:
      platform_stack_name: infrastructure-core-aws  # or your repo’s platform project name
      uv_index_prefix: ACCOUNT
      environment: ${{ github.event_name == 'workflow_dispatch' && github.event.inputs.environment || '' }}
      slug: ${{ github.event_name == 'workflow_dispatch' && github.event.inputs.slug || '' }}
      target: ${{ github.event_name == 'workflow_dispatch' && github.event.inputs.target || 'both' }}
    secrets:
      INFRA_GITHUB_APP_ID: ${{ secrets.INFRA_GITHUB_APP_ID }}
      INFRA_GITHUB_APP_PRIVATE_KEY: ${{ secrets.INFRA_GITHUB_APP_PRIVATE_KEY }}
      INFRA_GITHUB_TOKEN: ${{ secrets.INFRA_GITHUB_TOKEN }}
```

### Pulumi destroy app (GCP)

One stack per run (`environment` is `staging` or `prod`). Callers that need both envs dispatch twice (prod then staging).

```yaml
jobs:
  destroy:
    permissions:
      id-token: write
      contents: read
    uses: ExtensibilityAI/github-actions/.github/workflows/pulumi-destroy-app-gcp.yml@v2.6.0
    with:
      uv_index_prefix: EXT_STORE_INFRA_3320
      slug: ${{ github.event.inputs.slug }}
      environment: ${{ github.event.inputs.environment }}
    secrets:
      INFRA_GITHUB_APP_ID: ${{ secrets.INFRA_GITHUB_APP_ID }}
      INFRA_GITHUB_APP_PRIVATE_KEY: ${{ secrets.INFRA_GITHUB_APP_PRIVATE_KEY }}
      INFRA_GITHUB_TOKEN: ${{ secrets.INFRA_GITHUB_TOKEN }}
```

### Pulumi destroy app (AWS)

```yaml
jobs:
  destroy:
    permissions:
      id-token: write
      contents: read
    uses: ExtensibilityAI/github-actions/.github/workflows/pulumi-destroy-app-aws.yml@v2.6.0
    with:
      uv_index_prefix: ACCOUNT
      slug: ${{ github.event.inputs.slug }}
      environment: ${{ github.event.inputs.environment }}
    secrets:
      INFRA_GITHUB_APP_ID: ${{ secrets.INFRA_GITHUB_APP_ID }}
      INFRA_GITHUB_APP_PRIVATE_KEY: ${{ secrets.INFRA_GITHUB_APP_PRIVATE_KEY }}
      INFRA_GITHUB_TOKEN: ${{ secrets.INFRA_GITHUB_TOKEN }}
```

**Required caller secrets (GCP Pulumi):** `INFRA_GITHUB_APP_ID`, `INFRA_GITHUB_APP_PRIVATE_KEY` as **repository** Actions secrets, passed explicitly on the caller job (not `secrets: inherit`). Optional/legacy: `INFRA_GITHUB_TOKEN`. GCP jobs also need GitHub environment variable `PULUMI_BACKEND_URL` (`vars.PULUMI_BACKEND_URL`, written by `infra configure`).

**Required caller secrets (AWS Pulumi):** `INFRA_GITHUB_APP_ID`, `INFRA_GITHUB_APP_PRIVATE_KEY`. Optional/legacy: `INFRA_GITHUB_TOKEN`. AWS jobs need GitHub environment variable `PULUMI_BACKEND_URL` (S3 DIY backend, written by `infra configure`). No `PULUMI_ACCESS_TOKEN`.

**GCP vars:** `WIF_PROVIDER`, `GCP_SA`, `GCP_PROJECT_ID`, `GCP_REGION`, `PULUMI_BACKEND_URL` (as used by your stacks)

**AWS vars:** `AWS_ROLE_ARN`, `AWS_REGION`, `AWS_ACCOUNT_ID`, `PULUMI_BACKEND_URL`, `CODEARTIFACT_DOMAIN`, `CODEARTIFACT_DOMAIN_OWNER` (canonical/prod member that owns the domain; optional `CODEARTIFACT_REPOSITORY`, default `pypi`); for EKS deploy/destroy also `EKS_CLUSTER_NAME`, `K8S_NAMESPACE`, `HELM_RELEASE` (optional `EKS_REGION`, `IMAGE_REGISTRY`)

Composite actions that nest other composites **must** use fully-qualified `ExtensibilityAI/github-actions/<name>@vX.Y.Z` pins. Relative `./` paths resolve in the *caller* workspace and break cross-repo.
