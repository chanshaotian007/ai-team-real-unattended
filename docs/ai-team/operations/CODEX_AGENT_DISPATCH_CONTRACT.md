# Codex Agent Dispatch Contract

- 更新时间：`2026-04-05 22:35 +08:00`
- 目的：定义控制平面向真实 Codex agent 派发结构化任务时的最小协议

## 1. 适用范围

本协议仅用于：

- `delivery_mode: codex_agent`
- 由 `supervisor` 或后续 `dispatcher` 写入的 Codex agent outbox
- 真实 Codex agent 消费的结构化任务

本协议不替代现有：

- `agent_outbox`
- `work_orders`
- `commands / validation_commands`

这些能力仍服务于脚本化自动化与受控执行器。

## 2. 推荐 outbox

当前建议 outbox 文件：

- `docs/ai-team/operations/M1_M2_72H_CODEX_AGENT_DISPATCHES.jsonl`

每行一条 JSON。

## 3. 最小字段

```json
{
  "dispatch_id": "PLAN-S03-TASK-BE-RBAC-002-C#codex#1",
  "task_id": "PLAN-S03-TASK-BE-RBAC-002-C",
  "owner_role": "backend-agent",
  "summary": "backend codex task",
  "task_ref": "TASK-BE-RBAC-002-C",
  "shift_id": "S03",
  "delivery_mode": "codex_agent",
  "task_contract_version": "v1",
  "task_contract": {
    "task_id": "PLAN-S03-TASK-BE-RBAC-002-C",
    "owner_role": "backend-agent",
    "collaborators": ["qa-agent", "compliance-agent"],
    "goal": "补齐 RBAC 依赖链并收口审计字段",
    "constraints": ["必须保持 DM8 兼容"],
    "read_scopes": ["backend/**", "docs/**"],
    "write_scopes": ["backend/app/core/**", "backend/tests/**"],
    "artifacts": ["backend/app/core/security.py"],
    "acceptance_commands": ["pytest backend/tests/test_rbac_dependencies.py -q"],
    "risk_notes_required": true,
    "rollback_hint": "revert RBAC dependency changes"
  },
  "executor_rule": "backend-codex-dispatch",
  "emitted_at": "2026-04-05T22:35:00+08:00",
  "requested_by": "supervisor"
}
```

## 4. 执行语义

- `dispatch_id`
  - 同一任务的每次 Codex 派发都必须唯一。
- `owner_role`
  - 表示目标 Codex agent 角色。
- `summary`
  - 面向调度面板的短描述。
- `task_contract`
  - 面向真实 agent 的主协议，必须完整表达目标、边界和验收。
- `executor_rule`
  - 记录是由哪条自动化规则触发，便于追溯。

## 5. 控制平面责任

控制平面必须负责：

- 锁冲突检查
- 派发记录留痕
- 重复派发去重
- Gate 与运行态回写

控制平面不应负责：

- 代替真实 Codex agent 编码
- 伪造 agent 交付结果

## 6. 后续扩展字段

后续允许补充但不应破坏兼容性：

- `parent_task_id`
- `priority`
- `model_hint`
- `deadline`
- `handover_to`
- `followup_policy`
- `review_required`
