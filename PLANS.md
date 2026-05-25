# Standalone ai-team PLANS

## 4. Baseline Capability Matrix

| 需求章节 | 需求主题 | 交付物 | 主责 Agent | 验收口径 | 状态 |
|---|---|---|---|---|---|
| 5.1 | Codex Dispatch Bridge | `scripts/ai_team_codex_dispatch_runner.py` | orchestrator | 可初始化 dispatch/state，并支持 claim/complete/fail | Verified-Local |
| 5.2 | Codex Pilot Catalog | `scripts/ai_team_codex_pilot_seed.py`、dispatch/delivery contracts | orchestrator | 可校验锁、依赖与任务契约并投递 dispatch | Verified-Local |
| 5.3 | Git Save/Push Closure | `scripts/ai_team_git_repo_manager.py` | devops-agent | 可初始化仓库、提交并推送 | Verified-Local |
| 5.4 | GitLab MR / Reviewer Gate | `scripts/ai_team_gitlab_flow.py`、MR plan/report | orchestrator + devops-agent | 可发现项目、生成 MR payload，并在有 token 时创建或复用 MR | Verified-Local |
| 5.5 | Staging / Release / Rollback Gate | `scripts/ai_team_release_controller.py`、release state | devops-agent | 可记录 staging、验活、release、rollback 状态链 | Verified-Local |
| 5.6 | QA/UAT Baseline | `tests/`、`scripts/ai_team_codex_unattended.py` | qa-agent | 无人值守回归可跑通并产出 review | Verified-Local |
| 5.7 | PLANS Sync Report | `scripts/ai_team_plans_status_sync.py`、reports | orchestrator | 可根据 broker/evidence 生成 closeout 报告 | Verified-Local |

## 5. Initiative Execution Plans

<!-- ai-team:INIT-DEMO-001-PLAN -->
- INIT-DEMO-001-PLAN — 生成任务拆解、依赖和执行计划：Demo approved flow
<!-- ai-team:INIT-DEMO-002-PLAN -->
- INIT-DEMO-002-PLAN — 生成任务拆解、依赖和执行计划：Demo green flow
AI_TEAM_MARKER_INIT_DEMO_003_PLAN
- INIT-DEMO-003-PLAN — 生成任务拆解、依赖和执行计划：Demo passing flow
AI_TEAM_MARKER_INIT_ENH_001_PLAN
- INIT-ENH-001-PLAN — 生成任务拆解、依赖和执行计划：Enhanced delivery flow
