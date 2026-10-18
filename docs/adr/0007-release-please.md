# 0007. Release the whole repo with one version via release-please, using a GitHub App token

- **Status:** Accepted
- **Date:** 2026-10-18

## Context

We want automated releases: a CHANGELOG and version tags generated from the Conventional Commit titles that already land on `main` (PRs are squash-merged with the PR title as the commit message).

Constraints:

1. The repo is a monorepo (`web/`, `worker/`, `print/`, `supabase/`), but none of the packages is published to a registry. They are deployed together, and a feature usually touches several of them (migration, worker, web).
2. `worker/uv.lock` and `print/uv.lock` record each project's own version, and CI runs `uv sync --locked`. If a tool bumps `version` in `pyproject.toml` without regenerating the lock, CI fails.
3. `main` is protected by a ruleset that requires the `ci-ok` check. GitHub doesn't start other workflows for events caused by the default `GITHUB_TOKEN` (this prevents infinite workflow loops). A release PR opened with that token would never get `ci-ok`, so it couldn't be merged.

## Decision

We will use [release-please](https://github.com/googleapis/release-please) through `googleapis/release-please-action@v5`, in manifest mode with **one package at the repo root** (`"."`, `release-type: simple`):

- One version for the whole repo, in `version.txt`, with one root `CHANGELOG.md` and tags `vX.Y.Z`.
- First release `0.1.0` (`initial-version`), then normal SemVer from commit types. `bump-minor-pre-major` keeps breaking changes on `0.x` until we decide to ship `1.0.0`.
- `ci`, `docs` and `refactor` get visible changelog sections alongside `feat`/`fix`/`perf`/`revert`, because much of this project's work is infrastructure. `chore`, `test`, `build` and `style` stay hidden.
- The `version` fields in `package.json` / `pyproject.toml` are left alone (constraint 2, and nothing reads them).

The workflow mints a short-lived token from a **GitHub App** (`actions/create-github-app-token`) when `vars.RELEASE_APP_CLIENT_ID` and `secrets.RELEASE_APP_PRIVATE_KEY` are set. Events caused by an App token do trigger workflows, so CI runs on the release PR. Without them, it falls back to `GITHUB_TOKEN` with a warning. In that case, a human closes and reopens the release PR right before merging, which starts CI.

## Alternatives considered

- **Per-package releases** (`web`, `worker`, `print` each with their own version, changelog and tags `worker-v0.3.0`): more accurate per component, but for a solo project deployed as one unit it means three changelogs to read, a combined release PR to reason about, and per-package lockfile bumping to solve. We can split later by adding packages to the config.
- **Fine-grained personal access token** as the release token: simpler to set up than an App, but tied to the owner's account, long-lived (max 1 year, then releases silently break), and every release PR would look authored by the owner. An App token expires after an hour and acts as a separate bot identity.
- **`GITHUB_TOKEN` only, plus manual close/reopen:** no setup, but an easy-to-forget manual step on every release. Kept only as the fallback.
- **semantic-release / changesets:** semantic-release releases on every merge (no review step); changesets wants a file per change and is JS-centric. release-please's reviewable release PR fits GitHub Flow best.

## Consequences

- Merging a PR to `main` updates (or opens) the release PR. Merging the release PR creates the tag and GitHub Release. Nothing is deployed by a release yet; deploys still happen on merge to `main`.
- PR titles matter more: `feat:` bumps minor, `fix:` bumps patch, `!` / `BREAKING CHANGE:` marks a breaking change (minor while on `0.x`). A `Release-As: x.y.z` footer in a commit body forces a version.
- The owner must create and install the GitHub App and enable "Allow GitHub Actions to create and approve pull requests" (see PR #76).
- If we ever want the version inside the apps (e.g. Sentry release names), read `version.txt` or the tag in CI rather than the package manifests.
