# Codex Agent Dispatch Contract

- 更新时间：`2026-05-25 00:00 +08:00`
- 目的：定义控制平面向真实 Codex agent 派发结构化任务时的最小协议

## 1. 适用范围

本协议用于两类来源：

- `delivery_mode: codex_agent`
- 来自静态 pilot catalog 的任务
- 来自 initiative/task graph 的动态任务

本协议不替代现有：

- `agent_outbox`
- `work_orders`
- `commands / validation_commands`

这些能力仍服务于脚本化自动化与受控执行器。

## 2. 推荐 outbox

当前建议 outbox 文件：

- `docs/ai-team/operations/M1_M2_72H_CODEX_AGENT_DISPATCHES.jsonl`

每行一条 JSON。

## 3. v2 最小字段

```json
{
  "dispatch_id": "INIT-FOO-IMPLEMENT#codex#1",
  "task_id": "INIT-FOO-IMPLEMENT",
  "initiative_id": "INIT-FOO",
  "owner_role": "backend-agent",
  "summary": "initiative implementation",
  "task_ref": "INIT-FOO-IMPLEMENT",
  "shift_id": null,
  "delivery_mode": "codex_agent",
  "task_contract_version": "v2",
  "task_contract": {
    "task_id": "INIT-FOO-IMPLEMENT",
    "initiative_id": "INIT-FOO",
    "parent_task_id": "INIT-FOO",
    "task_type": "implementation",
    "phase": "execution",
    "approval_gate": {
      "required": true,
      "status": "approved",
      "reason": null
    },
    "execution_mode": "codex_agent",
    "batch_id": "INIT-FOO-BATCH-001",
    "owner_role": "backend-agent",
    "collaborators": ["qa-agent"],
    "goal": "按批准计划完成实现",
    "constraints": ["必须保持 DM8 兼容"],
    "read_scopes": ["scripts/**", "docs/**"],
    "write_scopes": ["scripts/**"],
    "artifacts": ["docs/ai-team/operations/init-foo_implementation.json"],
    "acceptance_commands": ["python3 scripts/ai_team_codex_dispatch_runner.py status --json"],
    "risk_notes_required": true,
    "rollback_hint": "revisit approved implementation output"
  },
  "executor_rule": "manual-codex-pilot-seed",
  "emitted_at": "2026-05-25T00:00:00+08:00",
  "requested_by": "orchestrator",
  "batch_id": "INIT-FOO-BATCH-001"
}
```

## 4. 执行语义

- `initiative_id`
  - 将 dispatch 绑定到一次需求/项目级工作项。
- `task_type`
  - 区分 `analysis/design/planning/implementation/qa/compliance/release`。
- `approval_gate`
  - 对 implementation 类任务是硬门；未批准任务只能显示为 `awaiting_approval`，不能 claim。
- `batch_id`
  - 表示该 dispatch 属于哪个已冻结的执行批次。
- `task_contract`
  - 仍是面向真实 agent 的主协议，必须完整表达目标、边界和验收。

## 5. 控制平面责任

控制平面必须负责：

- 锁冲突检查
- 派发记录留痕
- 重复派发去重
- Gate、approval、batch 与运行态回写

控制平面不应负责：

- 代替真实 Codex agent 编码
- 伪造 agent 交付结果

## 6. 兼容性

- `v1` 静态 pilot catalog dispatch 仍保留兼容。
- `v2` 在不破坏旧字段的前提下增加 initiative / approval / batch 语义。
