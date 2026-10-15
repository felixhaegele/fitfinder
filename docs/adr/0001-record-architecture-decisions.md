# 0001. Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-10-15

## Context

FitFinder is built incrementally over several milestones, partly as a learning project. Decisions such as "why a Postgres queue instead of Redis?" or "why Cloud Run?" get made once and then forgotten. Months later, nobody (including future-me or an AI assistant) knows whether a choice was deliberate or accidental, so it is either kept out of fear or changed without understanding the trade-offs.

## Decision

We will keep Architecture Decision Records (ADRs), in the lightweight format described by Michael Nygard ([Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)).

- One Markdown file per decision in `docs/adr/`, named `NNNN-short-title.md`, numbered sequentially.
- Each ADR has: Status, Date, Context, Decision, Alternatives considered, Consequences.
- ADRs are added in the same PR as the change they describe.
- ADRs are immutable once accepted. To change a decision, write a new ADR that supersedes the old one, and update only the old one's status line.
- Threshold: anything that would be expensive to reverse, or that a newcomer would ask "why?" about (new service, datastore, framework, deployment target, data-model shape, security or privacy approach).

## Alternatives considered

- **No written record / commit messages only:** cheap, but the reasoning gets scattered and is hard to find.
- **Wiki or Notion:** lives outside the repo, drifts from the code and isn't reviewed in PRs.

## Consequences

- Small overhead per significant decision (about 15 minutes).
- PR reviews can discuss the decision itself, not just the code.
- `docs/adr/` becomes a readable history of the architecture.
