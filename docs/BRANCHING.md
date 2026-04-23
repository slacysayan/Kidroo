# Branching strategy

Three long-lived branches:

| Branch | Role | Protection | Who pushes |
|---|---|---|---|
| `production` | Canonical production codebase. Fast-forward-only mirror of `main`. Deploy target for Railway + Vercel. | Protected — require linear history, require status checks, no force-push, no direct commits | Only the repo admin, only via fast-forward from `main` after CI is green on `main`. |
| `main` | Integration trunk. All feature PRs target `main`. | Protected — require PR review, require CI green, no force-push | CI, admins, and merge commits from PR bots. |
| `devin/<timestamp>-<slug>` | Short-lived feature branches. One PR per branch. | Unprotected. | Any contributor or coding agent. |

## Workflow

1. Cut a branch off `main`:
   ```
   git checkout main && git pull
   git checkout -b devin/$(date +%s)-my-feature
   ```
2. Push PRs into `main`. CI must go green before merge.
3. After the PR is squash-merged into `main`, the repo admin fast-forwards `production`:
   ```
   git checkout production && git pull
   git merge --ff-only origin/main
   git push origin production
   ```
   If this step rejects because `production` diverged, something was pushed out of band — stop and investigate rather than forcing.

## Branch protection rules (GitHub UI)

Apply these under **Settings → Branches → Add rule** for both `main` and `production`:

- ✅ Require a pull request before merging
  - `main`: 1 approval
  - `production`: 1 approval (or restrict pushes to admins)
- ✅ Require status checks to pass before merging
  - `Python (ruff + pytest)`
  - `Web (typecheck + lint)`
  - `Shell lint (SKILLS.sh)`
- ✅ Require branches to be up to date before merging
- ✅ Require linear history (`production` only — keeps the FF-only guarantee)
- ✅ Do not allow bypassing the above settings
- ❌ Do not allow force pushes
- ❌ Do not allow deletions

## Why three branches?

- `production` is the **only** branch any deploy target pulls from. That guarantees a single provenance for what's live.
- `main` lets CI churn without risking production.
- Short-lived `devin/*` branches keep PRs focused and collapsible.
