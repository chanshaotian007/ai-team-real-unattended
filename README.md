# ai-team-real-unattended

- Generated from `kernel-sense` at `2026-04-07T17:11:07.287414+08:00`
- Purpose: package the current `ai-team` control plane into a standalone unattended R&D team bootstrap project

## What This Project Includes

- Requirement/initiative intake: `scripts/ai_team_orchestrator.py`
- Approval and execution batch controller: `scripts/ai_team_approval.py`
- Autonomous batch workflow runner: `scripts/ai_team_autonomous_workflow.py`
- Full autonomy closeout runner: `scripts/ai_team_full_autonomy.py`
- Codex dispatch bridge: `scripts/ai_team_codex_dispatch_runner.py`
- Task seeding for catalog or initiative tasks: `scripts/ai_team_codex_pilot_seed.py`
- Unattended execution loop: `scripts/ai_team_codex_unattended.py`
- Initiative/task board projection: `scripts/ai_team_board.py`
- GitLab MR/reviewer bridge: `scripts/ai_team_gitlab_flow.py`
- PLANS closeout sync: `scripts/ai_team_plans_status_sync.py`
- Git save/push closure: `scripts/ai_team_git_repo_manager.py`
- Staging/release/rollback controller: `scripts/ai_team_release_controller.py`

## Quick Start

```bash
python3 scripts/ai_team_orchestrator.py create \
  --title "Add dashboard review flow" \
  --request-text "Add dashboard review flow and keep auditability" \
  --acceptance "board updated" \
  --json

python3 scripts/ai_team_approval.py approve --initiative-id INIT-ADD-DASHBOARD-REVIEW-FLOW-001 --json
python3 scripts/ai_team_codex_pilot_seed.py seed --source initiative --initiative-id INIT-ADD-DASHBOARD-REVIEW-FLOW-001 --all --json
python3 scripts/ai_team_autonomous_workflow.py --initiative-id INIT-ADD-DASHBOARD-REVIEW-FLOW-001 --batch-id INIT-ADD-DASHBOARD-REVIEW-FLOW-001-BATCH-001 --json
python3 scripts/ai_team_full_autonomy.py --initiative-id INIT-ADD-DASHBOARD-REVIEW-FLOW-001 --batch-id INIT-ADD-DASHBOARD-REVIEW-FLOW-001-BATCH-001 --json
python3 scripts/ai_team_board.py --json
```

## Lifecycle

The standalone ai-team now supports a minimal requirement-driven lifecycle:

1. create initiative from requirement text
2. generate analysis / design / planning / implementation / verification tasks
3. wait for explicit approval
4. create an execution batch on approval
5. seed only dispatch-ready tasks
6. run unattended execution against approved work
7. project board / PLANS / MR / release reports

## Compatibility

- Static pilot catalog flow is still supported for the original bootstrap tasks.
- Initiative-driven flow adds approval-aware dispatch and batch-aware unattended execution.
- `PLANS.md` remains the capability matrix; initiative-specific state lives under `docs/ai-team/operations/`.

## Autonomous Execution Log

<!-- ai-team:INIT-DEMO-001-IMPLEMENT -->
## INIT-DEMO-001-IMPLEMENT

- status: completed
- owner_role: frontend-agent
- goal: 按计划完成首轮实现：Demo approved flow
<!-- ai-team:INIT-DEMO-002-IMPLEMENT -->
## INIT-DEMO-002-IMPLEMENT

- status: completed
- owner_role: frontend-agent
- goal: 按计划完成首轮实现：Demo green flow
AI_TEAM_MARKER_INIT_DEMO_003_IMPLEMENT
## INIT-DEMO-003-IMPLEMENT

- status: completed
- owner_role: frontend-agent
- goal: 按计划完成首轮实现：Demo passing flow
AI_TEAM_MARKER_INIT_ENH_001_IMPLEMENT
## INIT-ENH-001-IMPLEMENT

- status: completed
- owner_role: frontend-agent
- goal: 按计划完成首轮实现：Enhanced delivery flow

