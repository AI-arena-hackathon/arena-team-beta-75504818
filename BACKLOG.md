# Backlog

<!-- IDEA: Replace this line with a one-line summary of what this product is
(e.g. "A habit tracker with streak reminders"). The README.md idea brief is
the authority on what to build; this file is the task list for building it. -->

Tasks are worked top-down by the build agent, one per turn where possible.
Update the sections every turn: move finished items to Done, hold the item
you're actively working on in In Progress, add follow-ups to Todo.

## Done

- [x] Initial scaffold seeded by the arena (AGENTS.md, BACKLOG.md, .gitignore, .env.example, .github/workflows/ci.yml)
- [x] Core backend API (health, clusters, actions, data refresh)
- [x] Frontend dashboard with voice guidance
- [x] Basic tests for backend endpoints

## In Progress

- [ ] Compliance & data handling: consent tracking, retention policies, disclaimers, PHI stripping

## Todo

- [ ] Replace the `<!-- IDEA: ... -->` placeholder at the top with a one-line summary of the actual idea
- [ ] Add consent tracking table and API endpoints
- [ ] Implement data retention policy (auto-cleanup of old records)
- [ ] Add PHI identifier stripping during data ingestion
- [ ] Add compliance disclaimers to UI (consent banner, data usage notice)
- [ ] Add tests for compliance features
- [ ] Make README.md reproduce how to run the project (commands + env vars, per .env.example)
- [ ] Keep `.github/workflows/ci.yml` green on every push (it runs tests)
- [ ] Wire product deploy: on CI green, build a preview (wrangler pages / docker image) and link it in README.md so judges can curl live product, not just repo
