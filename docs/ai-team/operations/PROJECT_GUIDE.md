# 项目说明与实际操作指引

## 1. 项目定位

`ai-team-real-unattended` 是一个面向研发自动化的 AI Team 控制平面与执行编排系统，目标是把：

- 需求分析
- 系统设计
- 任务拆解
- 审批
- 编码执行
- 测试验证
- MR 准备
- Release 门禁

串成一条可追踪、可审计、可自动推进的研发闭环。

它不是单点脚本自动化，而是一个“需求 → 计划 → 审批 → 执行 → 交付状态投影”的多 agent 协作控制面。

---

## 2. 核心能力

### 2.1 需求入口与 initiative 顶层对象
系统支持把自然语言需求注册为一个 `initiative`，作为后续分析、设计、拆解、审批、执行、交付的统一顶层对象。

关键文件：
- `scripts/ai_team_orchestrator.py`
- `docs/ai-team/operations/INITIATIVES.json`

### 2.2 自动分析、设计与任务拆解
围绕 initiative，系统会自动生成标准任务链：

- `analysis`
- `design`
- `planning`
- `implementation`
- `verification`

关键文件：
- `scripts/ai_team_orchestrator.py`
- `docs/ai-team/operations/INITIATIVE_TASKS.json`

### 2.3 多角色任务分工
项目使用角色模型表达协作边界，包括：

- `orchestrator`
- `frontend-agent`
- `backend-agent`
- `qa-agent`
- `devops-agent`

任务会根据类型和语义，被分配到不同角色，并附带：
- `read_scopes`
- `write_scopes`
- `acceptance_commands`
- `artifacts`

关键文件：
- `AGENTS.md`
- `scripts/ai_team_codex_pilot_seed.py`

### 2.4 审批与执行批次
implementation / verification 类任务不会在未审批时直接执行。审批通过后，系统会冻结一个 execution batch，并用它驱动后续自动交付链。

关键文件：
- `scripts/ai_team_approval.py`
- `docs/ai-team/operations/APPROVALS.json`
- `docs/ai-team/operations/EXECUTION_BATCHES.json`

### 2.5 审批后一键执行
审批通过后，可通过统一入口推进：

- 编码执行
- artifact 生成
- 验证动作执行
- Git / MR / Release 生命周期推进
- Board / Plans / Closeout 更新

关键脚本：
- `scripts/ai_team_autonomous_workflow.py`
- `scripts/ai_team_full_autonomy.py`

### 2.6 看板与状态投影
系统会将 initiative、task、batch、approval、MR、release 等状态投影到统一 board 中。

关键脚本：
- `scripts/ai_team_board.py`
- `docs/ai-team/reports/BOARD_STATE.json`

### 2.7 外部交付适配器
项目已接入以下适配器：

#### Git 适配器
- save
- push
- branch 规划/切换

脚本：
- `scripts/ai_team_git_repo_manager.py`

#### GitLab 适配器
- `plan-mr`
- `ensure-mr`
- `mr-status`
- `pipeline-status`
- `mr-note`

脚本：
- `scripts/ai_team_gitlab_flow.py`

#### Release 适配器
- `promote-staging`
- `run-check` / `verify`
- `promote-release`
- `rollback`

脚本：
- `scripts/ai_team_release_controller.py`

---

## 3. 当前形态

当前项目已经不是“脚本集合”，而是具备以下特征的 AI Team 自动交付控制面：

- initiative 顶层对象
- analysis/design/planning/implementation/verification 任务链
- approval gate
- execution batch
- autonomous execution entry
- board projection
- Git / MR / Release 适配器
- 交付证据与状态汇总

它能够完成一条最小闭环：

> 需求输入 → 自动分析 → 自动设计 → 自动计划 → 审批 → 自动执行编码/验证 → MR / Release 准备 → 看板与报告更新

---

## 4. 操作指引

### 4.1 使用前准备
确认当前位于项目根目录：

```bash
pwd
```

查看当前 git 状态：

```bash
git status --short
```

### 4.2 创建一个 initiative

```bash
python3 scripts/ai_team_orchestrator.py create \
  --initiative-id INIT-DEMO-100 \
  --title "Add dashboard review flow" \
  --request-text "Add dashboard review flow and keep auditability" \
  --acceptance "board updated" \
  --json
```

查看 initiative：

```bash
python3 scripts/ai_team_orchestrator.py show \
  --initiative-id INIT-DEMO-100 \
  --json
```

### 4.3 审批执行计划

```bash
python3 scripts/ai_team_approval.py approve \
  --initiative-id INIT-DEMO-100 \
  --approved-by tester \
  --note "approve demo" \
  --json
```

查看 approvals / batch：

```bash
python3 scripts/ai_team_approval.py list --json
```

### 4.4 将任务 seed 到 dispatch / broker

```bash
python3 scripts/ai_team_codex_pilot_seed.py seed \
  --source initiative \
  --initiative-id INIT-DEMO-100 \
  --all \
  --json
```

### 4.5 走统一自动执行入口

```bash
python3 scripts/ai_team_full_autonomy.py \
  --initiative-id INIT-DEMO-100 \
  --batch-id INIT-DEMO-100-BATCH-001 \
  --staging-command "python3 -m py_compile scripts/ai_team_generated_impl.py" \
  --verify-command "python3 -m py_compile scripts/ai_team_generated_impl.py" \
  --release-command "python3 -m py_compile scripts/ai_team_generated_impl.py" \
  --rollback-command "python3 -m py_compile scripts/ai_team_generated_impl.py" \
  --json
```

### 4.6 查看执行结果

查看 board：

```bash
python3 scripts/ai_team_board.py --json
```

查看 PLANS 同步：

```bash
python3 scripts/ai_team_plans_status_sync.py --json
```

查看 workflow 报告：

```bash
python3 -m json.tool docs/ai-team/reports/AUTONOMOUS_WORKFLOW.json
```

查看 MR 报告：

```bash
python3 -m json.tool docs/ai-team/reports/MR_PLAN.json
```

查看 release state：

```bash
python3 -m json.tool docs/ai-team/operations/RELEASE_CONTROLLER_STATE.json
```

---

## 5. 两种运行模式

### Local Simulation
适用于本地演练或缺少外部上下文时：
- 没有 GitLab token
- 没有 remote / deploy 上下文
- 没有真实 deploy command

系统此时可能产生：
- `planned_only`
- `blocked_missing_context`

但仍可生成：
- 本地 artifact
- board
- batch evidence
- MR / release 模拟报告

### External Lifecycle
适用于真实外部系统上下文完备时：
- 有 remote
- 有 GitLab token / project context
- 有 deploy / verify / rollback command

系统可推进：
- push
- ensure-mr
- mr-status
- pipeline-status
- staging verify
- promote-release / rollback

---

## 6. 成功判定

### 最低成功标准
- initiative 存在
- batch 存在
- tasks 已生成
- approval 已通过
- workflow 已执行完成

### 中间成功标准
- `AUTONOMOUS_WORKFLOW.json` 中存在 completed_tasks
- implementation 任务有 `changed_files`
- verification 任务有 `tests_run`

### 高等级成功标准
- `MR_PLAN.json` 已生成
- `RELEASE_CONTROLLER_STATE.json` 中有 staging / verify / release evidence
- board 中出现：
  - `Ready for MR`
  - `Ready for Release`

---

## 7. 常见问题排查

### initiative 不存在
```bash
python3 scripts/ai_team_orchestrator.py show --initiative-id INIT-DEMO-100 --json
```

### batch 不存在
```bash
python3 scripts/ai_team_approval.py list --json
```

### Git push 失败
检查：

```bash
git remote -v
git branch --show-current
python3 scripts/ai_team_git_repo_manager.py status --json
```

### MR 仍然是 planned_only / blocked_missing_context
检查：

```bash
python3 scripts/ai_team_gitlab_flow.py discover --json
python3 scripts/ai_team_gitlab_flow.py plan-mr --json
python3 scripts/ai_team_gitlab_flow.py mr-status --json
```

### Release blocked
检查：

```bash
python3 scripts/ai_team_release_controller.py status --json
python3 -m json.tool docs/ai-team/operations/RELEASE_CONTROLLER_STATE.json
```

---

## 8. 标准建议流程

```bash
python3 scripts/ai_team_orchestrator.py create \
  --initiative-id INIT-DEMO-100 \
  --title "Add dashboard review flow" \
  --request-text "Add dashboard review flow and keep auditability" \
  --acceptance "board updated" \
  --json

python3 scripts/ai_team_approval.py approve \
  --initiative-id INIT-DEMO-100 \
  --approved-by tester \
  --note "approve demo" \
  --json

python3 scripts/ai_team_codex_pilot_seed.py seed \
  --source initiative \
  --initiative-id INIT-DEMO-100 \
  --all \
  --json

python3 scripts/ai_team_full_autonomy.py \
  --initiative-id INIT-DEMO-100 \
  --batch-id INIT-DEMO-100-BATCH-001 \
  --staging-command "python3 -m py_compile scripts/ai_team_generated_impl.py" \
  --verify-command "python3 -m py_compile scripts/ai_team_generated_impl.py" \
  --release-command "python3 -m py_compile scripts/ai_team_generated_impl.py" \
  --rollback-command "python3 -m py_compile scripts/ai_team_generated_impl.py" \
  --json

python3 scripts/ai_team_board.py --json
python3 scripts/ai_team_plans_status_sync.py --json
```

---

## 9. 一句话总结

`ai-team-real-unattended` 是一个把 **需求、分析、设计、计划、审批、执行、验证、MR、Release、看板** 串起来的 AI Team 自动交付控制面，当前已经具备本地可运行闭环，并且正在向更真实的外部系统生命周期管理持续演进。
