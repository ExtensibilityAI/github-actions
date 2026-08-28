# Security Policy

## Reporting a vulnerability

If you believe you have found a security issue in this repository or in a reusable workflow/composite action defined here, please report it privately:

1. Email **security@extensibility.ai** with a description, reproduction steps, and impact assessment.
2. Do **not** open a public GitHub issue for undisclosed vulnerabilities.

We aim to acknowledge reports within **3 business days** and will coordinate disclosure once a fix is available.

## Scope

This library provides **GitHub Actions composites and reusable workflows**. Security responsibilities are shared:

| Party | Responsibility |
| --- | --- |
| **This repo** | Safe defaults, input validation, secret masking, documented threat model |
| **Callers** | WIF/IAM binding, GitHub Environment protection, minimal secrets, branch filters |

## Caller audit checklist (before production deploy)

Use this when onboarding a new repository that consumes `ExtensibilityAI/github-actions`:

### Identity and access

- [ ] GCP Workload Identity Federation provider restricts `attribute.repository` to the caller repo (see example below).
- [ ] AWS OIDC role trust policy restricts `sub` / `aud` to the caller repo and environment.
- [ ] No long-lived cloud access keys in GitHub secrets for GCP deploy paths.
- [ ] `prod` GitHub Environment has **required reviewers** and is only reachable from protected branches/tags.

### Workflow triggers

- [ ] Deploy workflows run on `push` to `main` (or release tags) — not on arbitrary branches.
- [ ] Pull requests use `staging` only (via `set-deploy-env`) and do not deploy to production.
- [ ] No `pull_request_target` deploy jobs with elevated secrets from fork PRs.

### Secrets

- [ ] Prefer explicit `secrets:` mappings over blanket `secrets: inherit` when only a subset is needed.
- [ ] `migration_extra_env` is passed as a **workflow_call secret**, never in `with:` inputs.
- [ ] Pulumi and GitHub App credentials are scoped to the minimum stacks/repos required.

### Pinning

- [ ] Pin exact semver tags (`@v2.1.2`) or commit SHAs — not `@main`, `@trunk`, or floating `@v2` in production.

## Example GCP WIF repository binding

Bind the GitHub OIDC principal to a single repository:

```json
{
  "attribute.repository": "ExtensibilityAI/my-app",
  "attribute.repository_owner": "ExtensibilityAI"
}
```

In IAM, use a condition on the workload identity pool provider so only matching repositories can impersonate deploy service accounts.

## Supported versions

Security fixes are applied to the latest `v2.x.y` release. Upgrade callers promptly when a security release is announced.
