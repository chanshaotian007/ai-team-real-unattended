# Codex Team Launch Runbook

- 更新时间：`2026-04-07 12:40 +08:00`
- 目标：把当前 `ai-team` 从“控制平面已就绪”推进到“真实 Codex agent 可以值守并接手研发任务”

## 1. 前提

启动前必须满足：

- `PLANS.md`、`AGENTS.md`、任务卡模板已冻结当前口径
- `docs/ai-team/operations/CODEX_MULTI_AGENT_CLOSED_LOOP_TARGET.md` 已作为目标定义
- `docs/ai-team/operations/CODEX_AGENT_DISPATCH_CONTRACT.md` 与 `docs/ai-team/operations/CODEX_AGENT_DELIVERY_CONTRACT.md` 已评审
- `AUTOMATIONS_CODEX_AGENT_PILOT.yaml` 保持 `enabled: false`

## 2. 首批角色

建议先启 4 条线：

- `orchestrator`
- `backend-agent`
- `frontend-agent`
- `qa-agent`

第二批再纳入：

- `compliance-agent`
- `probe-agent`
- `devops-agent`

## 3. 首批试点任务

优先选择：

- `TASK-BE-RBAC-002-C`
- `TASK-BE-RBAC-002-D`
- `TASK-BE-RBAC-002-E`
- `TASK-DASHBOARD-011`
- `TASK-RISK-VIZ-008-E`
- `TASK-PERF-017`
- `TASK-COMP-018`

原因：

- 写入边界清晰
- 验收方式明确
- 不涉及生产发布
- 适合通过 handover/result contract 进行跨角色协作

## 3.2 第二波 stretch

当首批 pilot 已完成并需要继续推进 backend 骨架任务时，按以下顺序纳入：

- `TASK-SYSCFG-012`
- `TASK-AI-STUB-014`
- `TASK-KNOWLEDGE-009`
- `TASK-SCA-010`
- `TASK-PROBE-LCM-013-A`
- `TASK-PROBE-LCM-013-B`
- `TASK-ST2-QA-REVIEW`
- `TASK-ST2-COMP-REVIEW`

说明：

- `CODEX_AGENT_PILOT_TASKS.yaml` 已为这 4 个任务补齐真实 owner、API 文件写边界和 acceptance commands
- `TASK-KNOWLEDGE-009`、`TASK-SCA-010` 通过 `depends_on_task_refs` 挂在 `Wave-ST1` 之后
- `M1_M2_72H_PLAN.json` 已补 `backend/app/api/** -> backend-agent` 锁，不再依赖空 write scopes 绕行
- `TASK-PROBE-LCM-013-A/B` 把脚本和 deploy 文档拆到 `probe-agent` / `devops-agent`，避免单任务跨锁写入
- `TASK-ST2-QA-REVIEW`、`TASK-ST2-COMP-REVIEW` 负责把 stretch 第二波从“代码已在”推进到“验证/合规有落盘结论”

## 3.3 D21-D30 收口波次

当 `D1-D20` 的 pilot catalog 已稳定、handover backlog 已压到 advisory-only 后，继续把 `D21-D30` 收口任务纳入：

- `TASK-DM8-015`
- `TASK-DEPLOY-016`
- `TASK-UAT-019`

说明：

- `TASK-DM8-015` 以既有 DM8 JDBC 与 direct Alembic 实证为前提，把迁移回归与门禁口径接入 Codex pilot catalog
- `TASK-DEPLOY-016` 依赖 `TASK-DM8-015` 与 `TASK-PROBE-LCM-013-C`，避免部署验证先于 DM8 / lifecycle 边界收口
- `TASK-UAT-019` 依赖 `TASK-DEPLOY-016`、`TASK-PERF-017`、`TASK-COMP-018`，保证总验收不跳过部署、性能和合规结论
- 这三项的纳入目标是“dispatch-ready + acceptance-defined”，不是把当前系统误表述成无限开放式无人值守研发

## 3.4 D31+ 扩展波次

当 `D1-D30` 已按封板口径收口后，继续把 deferred 的治理/兼容/HA/扩展验收项纳入：

- `TASK-OPENAPI-020`
- `TASK-HA-021`
- `TASK-COMPAT-022`
- `TASK-SEC-023`
- `TASK-QA-024`
- `TASK-UAT-025`

说明：

- `TASK-OPENAPI-020` 负责把 API 路由清单、错误响应与契约一致性继续收口到 backend 目录
- `TASK-HA-021` 负责把 HA/回滚/operator runbook 纳入 devops 作用域继续推进
- `TASK-COMPAT-022` 负责 probe 多架构/多 OS 的兼容 smoke 基线
- `TASK-SEC-023`、`TASK-QA-024`、`TASK-UAT-025` 按依赖链在 Wave-A 完成后继续派发
- `D31+` 仍属于“规则化扩展任务域”，不是开放式自治研发

## 3.1 真实导入入口

不要直接沿用压缩 plan 里的合并 owner。

- 真实 pilot 子任务、角色、写入边界以 `CODEX_AGENT_PILOT_TASKS.yaml` 为准
- `M1_M2_72H_PLAN.json` 继续作为 Gate/shift/file-lock 基线
- `scripts/ai_team_codex_pilot_seed.py` 负责把已校验的 pilot 子任务写入 `codex_agent` dispatch 队列

## 4. 值守命令

### 4.1 Orchestrator

统一值守看板：

```bash
python3 scripts/ai-team-monitor --watch 5
```

说明：

- monitor 现在会直接汇总 pilot catalog 的 `ready / blocked / active / completed` 状态
- monitor 会额外显示 `Handover Manual Review` 看板，用于值守 `manual_review_required` 的 handover 阻断项，并展示 `recommended_action` 与首条 `required_evidence`
- `Next Pilot Tasks` 会优先显示可继续派发或正在执行的 Codex 子任务
- 不需要额外跑一次 `ai_team_codex_pilot_seed.py list` 才能判断下一批可投递任务
- supervisor 开启 `global.codex_pilot.enabled=true` 后，会在每轮 tick 自动把 `ready` 且未派发的 pilot 子任务写入 codex dispatch 队列
- `global.codex_pilot.max_active_per_role` 与 `role_limits` 用来限制单角色并发，避免 backend/qa/compliance 在同一轮被过量占满
- pilot catalog 若补 `priority` 字段，supervisor 会优先派发数值更小的任务；未配置时默认按 `default_priority=100`
- 若上游 Codex 任务完成时在 `handover_notes` 里明确点名下游角色，supervisor 会把该依赖链上的 ready 下游 pilot 任务提升到普通 priority 之前
- `global.handover_dispatch.enabled=true` 时，supervisor 会把 open handover backlog 收敛成可升级候选；`preview_only=true` 仅展示候选，`preview_only=false` 才会按 allowlist 真的写入新的 dispatch/work order

初始化 Codex runtime 零态文件：

```bash
python3 scripts/ai_team_codex_dispatch_runner.py init --json
```

查看 pilot 目录：

```bash
python3 scripts/ai_team_codex_pilot_seed.py list --json
python3 scripts/ai_team_codex_pilot_seed.py show --task-ref TASK-BE-RBAC-002-C --json
```

看第二波 backend 任务是否 ready：

```bash
python3 scripts/ai_team_codex_pilot_seed.py list --role backend-agent --json
python3 scripts/ai_team_codex_pilot_seed.py show --task-ref TASK-KNOWLEDGE-009 --json
```

投递一批真实子任务：

```bash
python3 scripts/ai_team_codex_pilot_seed.py seed \
  --task-ref TASK-BE-RBAC-002-C \
  --task-ref TASK-BE-RBAC-002-D \
  --task-ref TASK-DASHBOARD-011 \
  --json
```

继续投递当前 catalog 中“未完成且已就绪”的第二波任务时，可直接按 task ref 选择：

```bash
python3 scripts/ai_team_codex_pilot_seed.py seed \
  --task-ref TASK-SYSCFG-012 \
  --task-ref TASK-AI-STUB-014 \
  --json
```

投递 `D31+` 首批扩展任务：

```bash
python3 scripts/ai_team_codex_pilot_seed.py seed \
  --task-ref TASK-OPENAPI-020 \
  --task-ref TASK-HA-021 \
  --task-ref TASK-COMPAT-022 \
  --json
```

查看 dispatch 队列：

```bash
python3 scripts/ai_team_codex_dispatch_runner.py list --json
python3 scripts/ai_team_codex_dispatch_runner.py status --json
```

从无人值守总验收入口推进当前 codex 队列：

```bash
python3 scripts/ai_team_codex_unattended.py --json
```

说明：

- 该入口会按当前 dispatch 队列自动执行 `claim -> acceptance -> complete/fail`
- 若下游 pilot 子任务因依赖满足而变为 `ready + unseeded`，会继续自动 `seed`
- 它只会基于 `CODEX_AGENT_PILOT_TASKS.yaml` 中已经定义好的 `acceptance_commands`、`artifacts` 和写边界推进，不代表开放式自治研发

按角色查看：

```bash
python3 scripts/ai_team_codex_dispatch_runner.py list --role backend-agent --json
python3 scripts/ai_team_codex_dispatch_runner.py status --role frontend-agent --json
```

### 4.2 角色 Agent

认领任务：

```bash
python3 scripts/ai_team_codex_dispatch_runner.py claim --role backend-agent --json
```

完成任务：

```bash
python3 scripts/ai_team_codex_dispatch_runner.py complete \
  --dispatch-id PLAN-S03-TASK-BE-RBAC-002-C#codex#1 \
  --message "backend codex task done" \
  --changed-file backend/app/core/security.py \
  --artifact backend/tests/test_rbac_dependencies.py \
  --test-result '{"command":"pytest backend/tests/test_rbac_dependencies.py -q","status":"passed"}' \
  --risk-note "needs final reviewer pass" \
  --handover-note "qa-agent should verify DM8 path" \
  --json
```

失败回写：

```bash
python3 scripts/ai_team_codex_dispatch_runner.py fail \
  --dispatch-id PLAN-S07-TASK-DASHBOARD-011#codex#1 \
  --message "frontend contract mismatch" \
  --risk-note "needs backend field alignment" \
  --json
```

## 5. 值守口径

Orchestrator 关注：

- seed 前先确认 `validation.ok=true`
- seed 前再确认 `readiness.ready=true`；blocked 任务不要硬放行
- Codex runner 的 `claim/complete/fail` 现在会直接同步 broker work order；依赖就绪态不需要再额外等待一次 supervisor reconcile
- 不把压缩 plan 的合并 owner 直接当成真实子任务 owner
- dispatch 是否有人认领
- 是否按 `owner_role` 归属正确
- `python3 scripts/ai_team_autopilot.py status --json` 现在必须同时看到 `pid`、`runner_pid`、`codex_runner_pid` 三条常驻进程都处于 `running`
- `python3 scripts/ai_team_codex_dispatch_runner.py status --json` 会自动压掉 broker 已 supersede 的历史 dispatch；若看到 `suppressed_superseded_count>0` 且 `pending=0`，表示只是历史重派记录，不是当前阻塞
- handover 是否明确指向下一角色
- completion 是否附带 changed files / tests / risk notes
- `handover_followup` completion 若缺少 `tests_run`，或在 `risk_notes_required=true` 时缺少 `risk_notes`，会被 supervisor 拒收并重新打开
- handover completion 被拒收时，supervisor 会自动给 `orchestrator` 追加一条 `FOLLOWUP-HANDOVER-*` 任务，要求对重开原因做处置或重新派发；该任务会携带 `recommended_action` 与 `required_evidence`
- `FOLLOWUP-HANDOVER-*` 执行后会输出两类明确结果：`handover_redispatch_ready:*` 表示已具备重新派发条件，`handover_review_required:*` 表示必须转人工审查
- 对 `handover_redispatch_ready:*`，control plane 会把原 handover 任务重新置回 `queued`，并授予一次性的 `redispatch_override_once`；该 override 只在下一次真实 dispatch 成功发出时消费
- `handover_dispatch.max_completion_rejections` 控制自动重派上限；达到阈值后该 handover 会停止自动 redispatch，并在 monitor 中显示为 `review_required`
- `global.handover_manual_review.stale_after_minutes` 定义人工 review 阻断项的超时阈值；超过阈值后，supervisor 会在 watch detail 和 runtime event 中打出 stale 告警
- `global.codex_pilot.manual_review_throttle` 默认以 `scope=owner_role_or_lineage` 运行：存在 stale handover review 积压时，会优先拦住同角色或同来源链路上的 pilot auto-seed；若配置了 `matched_quota_per_run`，则每轮可按 quota 低速放行少量命中任务。进一步可用 `matched_quota_mode=per_owner_role` 按角色分别分配预算，并结合 `matched_quota_decay_per_stale` 与 `matched_quota_min` 让各角色 quota 随各自 backlog 严重度自动收缩
- `global.handover_dispatch.manual_review_throttle` 采用同样的 `scope=owner_role_or_lineage` 口径：stale handover review 积压会优先阻止相关 handover follow-up 自动分发；若配置了 `matched_quota_per_run`，则只允许极少量命中 handover 低速继续流动，并可通过 `matched_quota_mode=per_owner_role` 和 `matched_quota_decay_per_stale` 在不同角色 backlog 变重时分别退化成更严格限流
- `scripts/ai_team_72h_orchestrator.py` 生成的状态报告、窗口报告和 handover 报告现在都会显式写出 `Pilot auto-seed` / `Handover auto-dispatch` 的 scoped throttle 状态与命中数量，便于值班判断是“全局停摆”还是“局部链路受阻”
- `scripts/ai-team-monitor`、`scripts/ai_team_72h_orchestrator.py` 和 `scripts/ai_team_closed_loop_check.py` 会继续带出 `throttle_oldest_backlog_by_role` 与命中任务的 `manual_review_priority_reason`，便于值班时直接判断“哪个角色最老 backlog 正在吃预算、哪条任务被优先放行”
- `python3 scripts/ai_team_closed_loop_check.py --json` 现在会同时写出 `handover_manual_review`、`pilot_seed_throttle` 和 `handover_dispatch_throttle`；默认把这些 backlog/throttle 记为 residual risk，在 Gate 场景仍应使用 `--assert-no-stale-manual-review`，把 stale review 升级成真正的验收失败
- `scripts/ai-team-monitor` 现在会同时展示 `throttle_allowed`、`throttle_blocked` 与 `quota`，值班时可以直接看出当前是“完全卡死”还是“在降速推进”
- `scripts/ai-team-monitor` 的 Codex Runner 摘要现在和 broker 当前真相对齐：历史 superseded dispatch 不再计入当前 `pending`，但会单独显示 `suppressed_superseded_count`
- monitor / codex runner 若出现 `reopened`，表示 agent 曾回写完成，但 broker 已把该 dispatch 重新打开，不能再按已完成计入口径
- 已完成任务默认不重复 seed；需要重跑时才使用 `--force`

角色 Agent 关注：

- 只认领本角色任务
- 只在 `write_scopes` 内修改
- 完成时必须附测试与 handover
- 遇到边界不清直接 `fail`，不要绕过协议

## 6. 放行标准

满足以下条件后，才允许从 pilot 进入更广泛项目任务：

- 至少 3 个任务完成 claim -> complete 全链路
- 至少 1 个任务完成 claim -> fail -> orchestrator follow-up 全链路
- monitor 能稳定显示 `codex_agent` delivery 摘要
- 没有跨角色越权写入
- 没有敏感信息进入通知或 monitor

## 7. 不纳入首批 pilot 的事项

- 生产发布
- 真实密钥轮换
- destructive migration
- 多主机批量运维
- 仓库外部系统的不可回滚操作
