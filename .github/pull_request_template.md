## Summary

<!-- What does this PR change, and why? -->

Closes #

## Type

- [ ] `feat`: new functionality
- [ ] `fix`: bug fix
- [ ] `chore` / `ci` / `docs` / `refactor` / `test`

## Checklist

- [ ] PR title follows Conventional Commits (`feat: …`, `fix: …`)
- [ ] Lint, typecheck and tests pass locally for every package touched
  - web: `pnpm lint && pnpm typecheck && pnpm test`
  - worker: `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest`
- [ ] DB change: added a **new** migration, RLS policies included, TS types regenerated
- [ ] New env var added to `.env.example`
- [ ] Measurement fixtures still within tolerance, or the change is deliberate and explained below
- [ ] ADR added in `docs/adr/` if this is a non-trivial architecture decision
- [ ] No secrets, personal data or user images committed

## How to test

<!-- Steps a reviewer can follow. Screenshots for UI changes. -->
