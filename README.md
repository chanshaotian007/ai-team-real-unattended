# ai-team-real-unattended

一个独立的 AI Team 控制平面，用于把一个需求转化为可追踪的 initiative、自动生成交付计划、等待审批，并通过统一入口推进编码、验证、MR 准备与 release readiness。

A standalone AI-team control plane for turning a requirement into a tracked initiative, generating a delivery plan, waiting for approval, and then driving coding, verification, MR preparation, and release readiness through a single automation entrypoint.

## Table of Contents / 目录

- [Highlights / 项目亮点](#highlights--项目亮点)
- [What this repository is / 项目定位](#what-this-repository-is--项目定位)
- [Core components / 核心组件](#core-components--核心组件)
- [Quick start / 快速开始](#quick-start--快速开始)
- [Workflow overview / 工作流概览](#workflow-overview--工作流概览)
- [Operating modes / 运行模式](#operating-modes--运行模式)
- [Status model at a glance / 状态模型概览](#status-model-at-a-glance--状态模型概览)
- [Architecture / 架构说明](#architecture--架构说明)
- [State Machine / 状态机](#state-machine--状态机)
- [Contributing / 参与贡献](#contributing--参与贡献)
- [Development workflow / 开发工作流](#development-workflow--开发工作流)
- [Current scope and boundary / 当前范围与边界](#current-scope-and-boundary--当前范围与边界)
- [FAQ / 常见问题](#faq--常见问题)
- [Roadmap / 路线图](#roadmap--路线图)
- [Next places to look / 推荐继续阅读](#next-places-to-look--推荐继续阅读)

## Highlights / 项目亮点

- Requirement-driven workflow: initiative -> analysis -> design -> planning -> implementation -> verification
- 需求驱动工作流：initiative -> 分析 -> 设计 -> 计划 -> 实现 -> 验证
- Explicit approval gate before execution
- 执行前的显式审批门
- Batch-based autonomous execution
- 基于 execution batch 的自主执行
- Board and PLANS projection for visibility
- 通过 Board 与 PLANS 提供可视化投影
- Git / GitLab MR / release-controller adapters
- Git / GitLab MR / release-controller 适配器
- Local simulation mode and external lifecycle mode
- 同时支持本地模拟模式与外部生命周期模式

## What this repository is / 项目定位

This project is an orchestration layer for multi-agent software delivery. It does not just run isolated scripts; it manages:

本项目是一个面向多 Agent 软件交付的编排层，而不是简单的脚本集合。它负责管理：

- initiative intake / 需求入口
- task decomposition / 任务拆解
- role assignment / 角色分工
- approval and execution batches / 审批与执行批次
- autonomous workflow execution / 自主执行链
- MR / release readiness projection / MR 与发布就绪态投影
- delivery evidence and reports / 交付证据与报告

If you want a fuller project introduction and runbook, see:
如果你需要更完整的项目介绍与操作手册，请参见：
- `docs/ai-team/operations/PROJECT_GUIDE.md`

## Core components / 核心组件

- Requirement/initiative intake / 需求入口：`scripts/ai_team_orchestrator.py`
- Approval and execution batch controller / 审批与执行批次控制器：`scripts/ai_team_approval.py`
- Autonomous batch workflow runner / 批次自主执行器：`scripts/ai_team_autonomous_workflow.py`
- Full autonomy lifecycle runner / 全链路自主生命周期入口：`scripts/ai_team_full_autonomy.py`
- Dispatch bridge / 派发桥接：`scripts/ai_team_codex_dispatch_runner.py`
- Task seeding for catalog or initiative tasks / 任务投递器：`scripts/ai_team_codex_pilot_seed.py`
- Board projection / 看板投影：`scripts/ai_team_board.py`
- Git adapter / Git 适配器：`scripts/ai_team_git_repo_manager.py`
- GitLab MR / pipeline adapter / GitLab MR 与流水线适配器：`scripts/ai_team_gitlab_flow.py`
- Staging / release / rollback adapter / staging / 发布 / 回滚适配器：`scripts/ai_team_release_controller.py`
- PLANS closeout sync / PLANS 收口同步：`scripts/ai_team_plans_status_sync.py`

## Quick start / 快速开始

```bash
python3 scripts/ai_team_orchestrator.py create \
  --title "Add dashboard review flow" \
  --request-text "Add dashboard review flow and keep auditability" \
  --acceptance "board updated" \
  --json

python3 scripts/ai_team_approval.py approve --initiative-id INIT-ADD-DASHBOARD-REVIEW-FLOW-001 --json
python3 scripts/ai_team_codex_pilot_seed.py seed --source initiative --initiative-id INIT-ADD-DASHBOARD-REVIEW-FLOW-001 --all --json
python3 scripts/ai_team_full_autonomy.py \
  --initiative-id INIT-ADD-DASHBOARD-REVIEW-FLOW-001 \
  --batch-id INIT-ADD-DASHBOARD-REVIEW-FLOW-001-BATCH-001 \
  --staging-command "python3 -m py_compile scripts/ai_team_generated_impl.py" \
  --verify-command "python3 -m py_compile scripts/ai_team_generated_impl.py" \
  --release-command "python3 -m py_compile scripts/ai_team_generated_impl.py" \
  --rollback-command "python3 -m py_compile scripts/ai_team_generated_impl.py" \
  --json
python3 scripts/ai_team_board.py --json
```

## Workflow overview / 工作流概览

1. Create an initiative from requirement text / 从需求文本创建 initiative
2. Generate analysis / design / planning / implementation / verification tasks / 自动生成分析、设计、计划、实现、验证任务
3. Wait for explicit approval / 等待显式审批
4. Freeze an execution batch / 冻结 execution batch
5. Seed dispatch-ready tasks / 投递可执行任务
6. Run the full autonomy lifecycle / 运行完整自主生命周期
7. Update board / PLANS / MR / release reports / 更新看板、PLANS、MR、release 报告

## Operating modes / 运行模式

### Local simulation / 本地模拟模式
Use this mode when external context is incomplete.
当外部上下文不完整时，使用本地模拟模式。

Typical outcomes may include / 典型结果可能包括：
- `planned_only`
- `blocked_missing_context`

The system still produces / 系统仍会产出：
- local artifacts / 本地产物
- batch evidence / 批次证据
- board projections / 看板投影
- MR / release reports / MR 与 release 报告

### External lifecycle / 外部生命周期模式
Use this mode when real integration context is available, for example:
当真实集成上下文完备时，使用外部生命周期模式，例如：
- configured remote / 已配置 remote
- GitLab token and project context / 已配置 GitLab token 与项目上下文
- deploy / verify / rollback commands / 已准备 deploy / verify / rollback 命令

In this mode the system can progress through / 在该模式下，系统可推进：
- push
- ensure-mr
- mr-status
- pipeline-status
- staging verification / staging 验证
- promote-release / rollback / 发布或回滚

## Status model at a glance / 状态模型概览

Typical delivery-facing states include / 典型交付状态包括：
- `Approved`
- `Ready for MR`
- `Ready for Release`
- `Blocked`
- `planned_only`
- `blocked_missing_context`

Board output is projected from initiative, batch, MR, pipeline, and release evidence rather than from a single status flag.
看板输出由 initiative、batch、MR、pipeline、release 等证据共同投影，而不是单个状态字段决定。

## Architecture / 架构说明

### High-level architecture / 高层架构

The project is organized as a control plane plus execution adapters:

本项目整体可以理解为“控制平面 + 执行适配器”的结构：

- **Control plane / 控制平面**
  - initiative intake / 需求入口
  - approval and execution batch management / 审批与执行批次管理
  - task dispatch and broker synchronization / 任务派发与 broker 同步
  - board / PLANS / report projection / 看板、PLANS 与报告投影

- **Execution plane / 执行平面**
  - autonomous workflow execution / 自主工作流执行
  - implementation / verification task progression / 实现与验证任务推进
  - artifact generation and evidence capture / 产物生成与证据留存

- **External adapters / 外部适配器**
  - Git save / push / branch strategy / Git 保存、推送与分支策略
  - GitLab MR / pipeline lifecycle / GitLab MR 与流水线生命周期
  - staging / release / rollback lifecycle / staging、发布与回滚生命周期

### Main runtime path / 主运行路径

A typical full run looks like this:

一条完整运行链通常如下：

1. `ai_team_orchestrator.py` creates an initiative  
   `ai_team_orchestrator.py` 创建 initiative
2. `ai_team_approval.py` freezes an execution batch  
   `ai_team_approval.py` 冻结 execution batch
3. `ai_team_codex_pilot_seed.py` seeds dispatch-ready tasks  
   `ai_team_codex_pilot_seed.py` 投递可执行任务
4. `ai_team_full_autonomy.py` orchestrates workflow + git + MR + release  
   `ai_team_full_autonomy.py` 串联 workflow、git、MR、release
5. `ai_team_board.py` and `ai_team_plans_status_sync.py` project final visibility  
   `ai_team_board.py` 与 `ai_team_plans_status_sync.py` 负责最终投影与可视化

## State Machine / 状态机

### Initiative lifecycle / Initiative 生命周期

Typical initiative states:

典型 initiative 状态包括：

- `planned` — requirement has been registered and tasks generated  
  已登记需求并生成任务
- `approved_for_execution` — approval passed, waiting for or entering execution  
  已通过审批，等待或进入执行
- `integration_ready` — workflow, MR/release readiness, and evidence are sufficient  
  workflow、MR/发布准备与证据已达到集成就绪
- `blocked` / `failed` / `rejected` — execution or external gate prevents progress  
  执行或外部门禁阻断推进

### Batch lifecycle / Batch 生命周期

Typical batch states:

典型 batch 状态包括：

- `approved` — frozen and allowed to execute  
  已冻结并允许执行
- `running` — autonomous workflow is actively processing tasks  
  自主工作流正在执行
- `completed` — internal workflow finished, external gates may still be pending  
  内部 workflow 已结束，但外部门禁可能仍未通过
- `integration_ready` — external lifecycle conditions are satisfied  
  外部生命周期条件满足，可进入更高一级交付

### Delivery-facing states / 面向交付的状态

The board and reports expose delivery-oriented states rather than only raw task completion:

看板与报告对外展示的是“交付语义状态”，而不只是任务完成状态：

- `Approved` — execution passed and evidence is present  
  执行完成且证据齐全
- `Ready for MR` — branch / push / MR lifecycle conditions are satisfied  
  分支、push、MR 生命周期条件满足
- `Ready for Release` — MR / pipeline / staging verification conditions are satisfied  
  MR、流水线、staging 验证条件满足
- `planned_only` — local plan exists but external context is not enough for real promotion  
  本地计划存在，但外部上下文不足以进入真实推进
- `blocked_missing_context` — a remote/token/project/deploy context is missing  
  缺失远端、token、项目或部署上下文
- `Blocked` — a real execution or external gate failure stops the flow  
  执行失败或外部门禁失败导致流程阻断

These states are projected from initiative status, batch verification summary, MR state, pipeline state, and release state together.
这些状态由 initiative 状态、batch 证据、MR 状态、pipeline 状态和 release 状态共同投影得出。

## Repository structure / 仓库结构

- `scripts/` — orchestration, adapters, and execution entrypoints  
  编排器、适配器与执行入口
- `docs/ai-team/operations/` — initiative state, approvals, batches, contracts, release state  
  initiative 状态、审批、批次、契约、release 状态
- `docs/ai-team/reports/` — board, MR, workflow, PLANS sync, and closeout reports  
  看板、MR、workflow、PLANS 同步与 closeout 报告
- `tests/` — script-level regression coverage  
  脚本级回归测试
- `PLANS.md` — capability matrix and execution-plan projection target  
  能力矩阵与执行计划投影目标

## Contributing / 参与贡献

We recommend treating this repository as a workflow-control project rather than a pure library.
推荐把这个仓库视为“工作流控制项目”，而不是纯函数库。

Typical contribution areas / 常见贡献方向：
- orchestration logic / 编排逻辑
- task contract and validation / 任务契约与校验
- board and report projection / 看板与报告投影
- Git / GitLab / release adapters / Git、GitLab、release 适配器
- documentation and runbooks / 文档与操作手册

Before making large behavioral changes, prefer to keep these invariants stable:
在做较大行为改动前，建议尽量保持以下不变量稳定：
- initiative -> batch -> task lifecycle remains traceable  
  initiative -> batch -> task 生命周期保持可追踪
- approval stays explicit before implementation-class work  
  implementation 类任务前始终保留显式审批门
- board and report outputs remain machine-readable  
  board 与报告输出保持机器可读
- local simulation mode should not be broken by external-mode changes  
  外部模式增强不应破坏本地模拟模式

### Suggested contribution flow / 建议贡献流程

1. create or identify an initiative / 创建或确认一个 initiative
2. update or inspect generated tasks / 更新或检查任务链
3. run approval-aware execution locally / 在本地执行审批后流程
4. inspect board / MR / release outputs / 检查 board、MR、release 输出
5. validate scripts and reports before committing / 提交前验证脚本与报告

## Development workflow / 开发工作流

### 1. Inspect current state / 查看当前状态

```bash
git status --short
python3 scripts/ai_team_board.py --json
python3 scripts/ai_team_plans_status_sync.py --json
```

### 2. Create a demo initiative / 创建演示 initiative

```bash
python3 scripts/ai_team_orchestrator.py create \
  --initiative-id INIT-DEMO-DEV \
  --title "Demo development flow" \
  --request-text "Test the ai-team lifecycle end to end" \
  --acceptance "board updated" \
  --json
```

### 3. Approve and seed tasks / 审批并投递任务

```bash
python3 scripts/ai_team_approval.py approve \
  --initiative-id INIT-DEMO-DEV \
  --approved-by tester \
  --note "approve dev flow" \
  --json

python3 scripts/ai_team_codex_pilot_seed.py seed \
  --source initiative \
  --initiative-id INIT-DEMO-DEV \
  --all \
  --json
```

### 4. Run full autonomy locally / 本地执行全链路

```bash
python3 scripts/ai_team_full_autonomy.py \
  --initiative-id INIT-DEMO-DEV \
  --batch-id INIT-DEMO-DEV-BATCH-001 \
  --staging-command "python3 -m py_compile scripts/ai_team_generated_impl.py" \
  --verify-command "python3 -m py_compile scripts/ai_team_generated_impl.py" \
  --release-command "python3 -m py_compile scripts/ai_team_generated_impl.py" \
  --rollback-command "python3 -m py_compile scripts/ai_team_generated_impl.py" \
  --json
```

### 5. Review outputs / 检查输出

```bash
python3 scripts/ai_team_board.py --json
python3 -m json.tool docs/ai-team/reports/AUTONOMOUS_WORKFLOW.json
python3 -m json.tool docs/ai-team/reports/MR_PLAN.json
python3 -m json.tool docs/ai-team/operations/RELEASE_CONTROLLER_STATE.json
```

### 6. Validate Python scripts / 验证 Python 脚本

```bash
python3 -m py_compile scripts/*.py
```

### 7. Commit and push / 提交并推送

If you are working on a delivery branch, confirm your branch and remote first:
如果你在交付分支上开发，先确认分支和远端：

```bash
git branch --show-current
git remote -v
```

Then commit and push as appropriate for your environment.
然后根据你的环境完成 commit 与 push。
## Current scope and boundary / 当前范围与边界

This repository is best understood as a controllable AI-team delivery control plane.
It already supports a full local closed loop and a partially externalized lifecycle.
The remaining depth comes from connecting it to real remote GitLab, CI, deployment, and rollback environments.

这个仓库本质上是一个可控的 AI Team 交付控制面。
它已经支持完整的本地闭环与部分外部化生命周期；剩余增强主要来自接入真实 GitLab、CI、部署与回滚环境。

## FAQ / 常见问题

### 1. Why does the system stop at `planned_only`?  
### 1. 为什么系统停在 `planned_only`？

This usually means the local delivery plan exists, but the external GitLab lifecycle cannot continue yet.
通常表示本地交付计划已经生成，但外部 GitLab 生命周期还无法继续推进。

Common reasons / 常见原因：
- GitLab token is missing / 缺少 GitLab token
- project context is incomplete / 项目上下文不完整
- remote branch is not yet pushable / 远端分支尚不可推送
- MR can be planned locally but not created remotely / 本地可生成 MR 计划，但无法远程创建 MR

### 2. What does `blocked_missing_context` mean?  
### 2. `blocked_missing_context` 是什么意思？

It means the system has enough local information to continue internally, but lacks required external context.
表示系统在本地层面可以继续，但缺少外部系统必需上下文。

Typical missing context / 常见缺失上下文：
- remote repository config / remote 仓库配置
- GitLab token / GitLab token
- GitLab project path or base URL / GitLab 项目路径或 base URL
- deploy / verify / rollback commands / deploy、verify、rollback 命令

### 3. What is the difference between `Blocked` and `blocked_missing_context`?  
### 3. `Blocked` 和 `blocked_missing_context` 有什么区别？

- `blocked_missing_context` means the flow cannot continue because required external context is absent.
- `Blocked` means the flow did run a real step, but that step failed.

- `blocked_missing_context` 表示缺少外部上下文，流程无法继续。
- `Blocked` 表示已经执行了真实步骤，但该步骤失败。

### 4. Why is a task in `Approved` instead of `Ready for MR`?  
### 4. 为什么任务停在 `Approved` 而不是 `Ready for MR`？

This usually means implementation and verification completed, but Git/MR lifecycle evidence is not sufficient yet.
通常表示实现和验证已经完成，但 Git/MR 生命周期证据还不够。

Check / 可检查：
- git save / push result / git save 与 push 结果
- MR plan / ensure result / MR 计划或 ensure 结果
- source branch / target branch validity / source / target branch 是否有效

### 5. Why is a task not in `Ready for Release`?  
### 5. 为什么任务没有进入 `Ready for Release`？

`Ready for Release` requires stronger evidence than `Ready for MR`.
`Ready for Release` 比 `Ready for MR` 要求更强的证据。

Typical requirements / 常见要求：
- MR lifecycle status is acceptable / MR 生命周期状态可接受
- pipeline status is acceptable / pipeline 状态可接受
- staging verification passed / staging 验证通过
- release gate is not blocked / release gate 没有被阻断

### 6. How do I inspect the current delivery evidence?  
### 6. 如何查看当前交付证据？

Use these files and commands / 可使用以下文件与命令：

```bash
python3 scripts/ai_team_board.py --json
python3 scripts/ai_team_plans_status_sync.py --json
python3 -m json.tool docs/ai-team/reports/AUTONOMOUS_WORKFLOW.json
python3 -m json.tool docs/ai-team/reports/MR_PLAN.json
python3 -m json.tool docs/ai-team/operations/RELEASE_CONTROLLER_STATE.json
```

### 7. How do I run with real external commands?  
### 7. 如何接入真实外部命令运行？

Pass commands to the full runner:
通过 full runner 传入命令：

```bash
python3 scripts/ai_team_full_autonomy.py \
  --initiative-id INIT-DEMO-100 \
  --batch-id INIT-DEMO-100-BATCH-001 \
  --staging-command "<real staging deploy command>" \
  --verify-command "<real verification command>" \
  --release-command "<real production release command>" \
  --rollback-command "<real rollback command>" \
  --json
```

### 8. Where should I start debugging?  
### 8. 出问题时应从哪里开始排查？

Recommended order / 推荐顺序：
1. `python3 scripts/ai_team_board.py --json`
2. `python3 -m json.tool docs/ai-team/reports/AUTONOMOUS_WORKFLOW.json`
3. `python3 -m json.tool docs/ai-team/reports/MR_PLAN.json`
4. `python3 -m json.tool docs/ai-team/operations/RELEASE_CONTROLLER_STATE.json`
5. `python3 scripts/ai_team_gitlab_flow.py discover --json`
6. `python3 scripts/ai_team_git_repo_manager.py status --json`

## Roadmap / 路线图

### Near term / 近期目标

- Make Git branch strategy more production-like  
  让 Git 分支策略更贴近真实生产环境
- Strengthen MR lifecycle from `plan-mr` to `ensure-mr -> mr-status -> pipeline-status`  
  将 MR 生命周期从 `plan-mr` 强化到 `ensure-mr -> mr-status -> pipeline-status`
- Tighten release gates so staging verification and release actions are evidence-driven  
  让 release gate 更依赖 staging 验证与真实证据
- Improve board semantics for `planned_only`, `blocked_missing_context`, and `Blocked`  
  细化 `planned_only`、`blocked_missing_context`、`Blocked` 的看板语义

### Mid term / 中期目标

- Connect the full runner to a real GitLab project with token-backed MR lifecycle  
  将 full runner 接入真实 GitLab 项目，并使用 token 驱动 MR 生命周期
- Use real deploy / verify / rollback commands instead of local simulation defaults  
  使用真实 deploy / verify / rollback 命令替代本地模拟默认值
- Make pipeline results a hard gate for release readiness  
  让 pipeline 结果成为发布就绪的硬门
- Expand implementation tasks to touch richer business code paths  
  让 implementation 任务覆盖更丰富的业务代码路径

### Long term / 长期目标

- Evolve from local orchestration to environment-aware production delivery control  
  从本地编排演进到面向真实环境的生产交付控制面
- Support richer rollout strategies such as staged release, canary, and guarded rollback  
  支持分阶段发布、canary 与受控回滚等更复杂策略
- Build stronger delivery policies around approvals, mergeability, pipeline health, and deploy evidence  
  在审批、可合并性、流水线健康度和部署证据之上构建更强交付策略
- Make the system a reusable AI-team delivery framework rather than a single project bootstrap  
  让系统演进成可复用的 AI Team 交付框架，而不只是单项目 bootstrap

### Future work / 后续工作

Potential next steps include:
后续可继续推进的方向包括：

- richer branch naming and branch protection strategies  
  更丰富的分支命名与分支保护策略
- explicit merge / post-merge / release promotion lifecycle phases  
  更明确的 merge、post-merge 与 release promotion 生命周期阶段
- deeper environment-specific deployment integrations  
  更深的环境级部署集成
- more scenario-based regression coverage across Git, MR, pipeline, and release flows  
  针对 Git、MR、pipeline、release 流程的更多场景化回归覆盖

## Next places to look / 推荐继续阅读

- Project and operations guide / 项目说明与操作手册：`docs/ai-team/operations/PROJECT_GUIDE.md`
- Dispatch contract / 派发契约：`docs/ai-team/operations/CODEX_AGENT_DISPATCH_CONTRACT.md`
- Delivery contract / 交付契约：`docs/ai-team/operations/CODEX_AGENT_DELIVERY_CONTRACT.md`
- Capability matrix / 能力矩阵：`PLANS.md`

