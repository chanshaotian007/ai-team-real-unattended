# ai-team-real-unattended

- Generated from `kernel-sense` at `2026-04-07T17:11:07.287414+08:00`
- Purpose: package the current `ai-team` control plane into a standalone unattended R&D team bootstrap project

## What This Project Includes

- Codex dispatch bridge: `scripts/ai_team_codex_dispatch_runner.py`
- Curated pilot task seeding: `scripts/ai_team_codex_pilot_seed.py`
- Unattended execution loop: `scripts/ai_team_codex_unattended.py`
- GitLab MR/reviewer bridge: `scripts/ai_team_gitlab_flow.py`
- PLANS closeout sync: `scripts/ai_team_plans_status_sync.py`
- Git save/push closure: `scripts/ai_team_git_repo_manager.py`
- Staging/release/rollback controller: `scripts/ai_team_release_controller.py`

## Quick Start

```bash
python3 scripts/ai_team_codex_dispatch_runner.py init --json
python3 scripts/ai_team_codex_unattended.py --json
python3 scripts/ai_team_git_repo_manager.py status --json
```

## Unattended Loop

The bootstrap catalog is intentionally small and self-verifying:

1. dispatch bridge health
2. pilot catalog and dispatch contract health
3. git save/push closure health
4. GitLab MR/reviewer plan
5. release controller health
6. qa validation
7. PLANS closeout

After the unattended loop completes, `PLANS.md` should be upgraded to `Verified-Local` for the shipped baseline rows.
