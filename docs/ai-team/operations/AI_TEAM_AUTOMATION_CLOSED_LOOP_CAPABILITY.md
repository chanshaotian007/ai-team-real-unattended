# AI Team 自动化闭环处置能力说明

- 更新时间：`2026-04-07 12:40 +08:00`
- 适用范围：`kernel-sense` 仓库内 `ai-team` 本地自动化运行栈
- 当前结论：项目内既定规则驱动的自动化闭环已落地，可无人值守运行
- 当前阶段：`D1-D30` 已封板；`D31+` 扩展波次已进入同一套 dispatch 控制面

## 1. 当前运行态

- `autopilot`：`running`
- `supervisor`：`running`
- `agent_runner`：`running`
- `codex_runner`：`running`
- 最新闭环检查：`python3 scripts/ai_team_closed_loop_check.py --json` -> `overall.status=ok`
- 最新运行态监控：`python3 scripts/ai-team-monitor --json` -> `72h 关键链路闭环完成`

## 2. 已具备能力

### 2.1 调度与派发

- `autopilot` 可常驻守护 `supervisor`、`agent_runner` 与 `codex_runner`，脱离交互终端后仍可持续运行。
- `supervisor` 可按 `docs/ai-team/automations/AUTOMATIONS_M1_M2_72H.yaml` 自动执行 cron/workflow。
- `PLAN-*` 任务可按班次时间窗自动入队、派发、重试、回写状态。
- 文件锁与 `write_scope` 已进入 broker 管控，避免同一路径被并发修改。
- `CODEX_AGENT_PILOT_TASKS.yaml` 现已把 `D1-D30` 范围内可诚实定义 owner/read/write/acceptance 的 Codex pilot 子任务纳入 catalog，覆盖到：
  - `TASK-DM8-015`
  - `TASK-DEPLOY-016`
  - `TASK-UAT-019`
- `D31+` 首批扩展任务也已按同一口径进入 catalog：
  - `TASK-OPENAPI-020`
  - `TASK-HA-021`
  - `TASK-COMPAT-022`
  - `TASK-SEC-023`
  - `TASK-QA-024`
  - `TASK-UAT-025`

### 2.2 受控执行

- `agent_outbox -> agent_runner -> notification -> runtime` 已接通，不再依赖人工抄结果。
- 当前可自动执行的受控动作包括：
  - `scripts/deploy_controlled_exec.py`
  - `scripts/dm8_controlled_exec.py`
  - `scripts/ssh_controlled_exec.py`
- 当前已验证的真实链路包括：
  - 远端环境探测
  - 远端漂移检查
  - DM8 远端 Alembic 探测
  - 闭环检查
  - 后端测试、QA 回归、合规扫描

### 2.3 通知回写与运行态同步

- `agent_runner` 会将 `running/completed/errored` 通知写入 `M1_M2_72H_AGENT_NOTIFICATIONS.jsonl`。
- `supervisor` 会消费通知并回写：
  - `M1_M2_72H_AGENT_RUNTIME.json`
  - `M1_M2_72H_AGENT_BROKER.json`
  - monitor/agent board 展示态
- `monitor` 已可直接展示：
  - queue
  - agent_board
  - supervisor / runner / codex runner 心跳
  - 当前任务状态与最近事件
  - Codex dispatch 当前口径与 superseded 历史压缩计数
- handover 已区分为两类：
  - 落在自动派发范围内的 follow-up 才进入无人值守队列并继续闭环
  - 纯 advisory / 条件性提醒只保留在 handover 报表，不再长期占住 runtime queue 或 agent pending

### 2.4 自愈与重试

- 对 `PLAN-*` 的临时执行失败，`supervisor` 会在班次窗口内自动重试。
- 对旧版本遗留的 `blocked` 计划任务，已补兼容恢复逻辑，可自动重排。
- 对“runner 已执行但 supervisor 漏吞通知”的情况，已补 `runner_state` 对账自愈。
- 已验证真实恢复案例：
  - `PLAN-S09-TASK-DEPLOY-016` 首次因 SSH known_hosts 噪声误判失败
  - 新逻辑自动恢复并以 `#2` 工单重新执行
  - 最终自动完成，无需人工逐项干预

### 2.5 GitLab 闭环

- `supervisor` 已接通 GitLab project loop。
- 当前已支持：
  - issue/todo 轮询
  - issue note 回写
  - pipeline 失败后自动 retry
  - retry 仍失败时进入 follow-up / blocked 升级

## 3. 当前边界

以下能力已经明确具备边界，不应误解为无限开放式自治：

- 仅对“规则已定义、执行器已接入、作用域已授权”的任务实现无人值守闭环。
- 不是通用型“任意需求自动拆解、自动改全仓、自动上线”的开放式自治系统。
- 对规则范围外事项，当前策略是：
  - 自动发现
  - 自动记账/阻断/升级
  - 等待新规则或人工确认后再纳入闭环
- 代码改动层面目前仍以受控脚本、固定命令、固定作用域为主，不允许任意 shell 自由执行。

## 4. 何谓“已实现无人值守”

在当前项目里，“无人值守”成立的前提是以下链路闭合：

1. 任务由 plan/workflow 自动入队。
2. `supervisor` 自动判断是否到执行窗口、是否满足锁条件。
3. `agent_runner` 自动消费工单并调用受控执行器。
4. `codex_runner` 自动维持 dispatch lane 心跳、当前状态汇总与 broker 对账。
5. `scripts/ai_team_codex_unattended.py` 可作为无人值守总验收入口，对已规则化的 codex pilot 任务自动执行 `claim -> acceptance -> complete/fail -> seed downstream`。
6. 执行结果自动通知回写。
7. 运行态、队列、broker、monitor 自动同步。
8. 临时失败可自动重试；通知丢失或旧阻断可自动自愈。

以上链路当前都已落地并可按入口命令实跑验证。

## 5. 尚未纳入全自动闭环的部分

以下仍属于“项目自动化边界外”或“需要继续扩充规则”的部分：

- 新功能研发本身的开放式代码生成与自动合并
- Codex pilot dispatch 之后，当前已可通过 `scripts/ai_team_codex_unattended.py` 进入无人值守 claim/complete 流；但这仍然只覆盖 `CODEX_AGENT_PILOT_TASKS.yaml` 中已规则化的任务，不应误表述为任意需求都会自动编码并自动验收完成
- `D31+` 当前可按同一入口推进，但仍属于“已规则化扩展任务”而非开放式自主研发
- 未定义 `executor_rule` 的新类型任务
- 仓库外部系统的任意变更
- 需要高风险人工审批的发布动作
- 没有受控执行器封装的浏览器、数据库、远端运维新能力

这类事项要进入无人值守，必须先补：

- 任务匹配规则
- 受控执行器
- 回写协议
- 验收命令
- 失败重试与升级策略

## 6. 推荐验活命令

- `python3 scripts/ai_team_autopilot.py status --json`
- `python3 scripts/ai-team-monitor --json`
- `python3 scripts/ai_team_closed_loop_check.py --json`
- `python3 scripts/ai_team_codex_unattended.py --json`
- `python3 scripts/check_ai_team_host_tools.py`

建议至少同时满足以下口径：

- `autopilot.status=running`
- `supervisor.status=running`
- `runner.status=running`
- `codex_runner.status=running`
- `codex_runner.counts.pending=0`
- `overall.status=ok`

## 7. 关键落地点

- 自动化规则：`docs/ai-team/automations/AUTOMATIONS_M1_M2_72H.yaml`
- 监督器：`scripts/ai_team_supervisor.py`
- 守护器：`scripts/ai_team_autopilot.py`
- 执行适配器：`scripts/ai_team_agent_runner.py`
- Codex dispatch 守护：`scripts/ai_team_codex_dispatch_runner.py`
- Codex 无人值守总验收入口：`scripts/ai_team_codex_unattended.py`
- 运行态：`docs/ai-team/operations/M1_M2_72H_AGENT_RUNTIME.json`
- broker：`docs/ai-team/operations/M1_M2_72H_AGENT_BROKER.json`
- 工单流：`docs/ai-team/operations/M1_M2_72H_AGENT_WORK_ORDERS.jsonl`
- 通知流：`docs/ai-team/operations/M1_M2_72H_AGENT_NOTIFICATIONS.jsonl`

## 8. 一句话结论

`ai-team` 现在已经具备项目内可落地的自动化闭环处置能力，且当前运行态健康；但其自治范围仍是“已规则化、已受控封装、已定义验收”的任务域，而不是无限开放式自主研发系统。
