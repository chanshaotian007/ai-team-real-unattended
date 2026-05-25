# Codex Agent Delivery Contract

- 更新时间：`2026-05-25 00:00 +08:00`
- 目的：定义真实 Codex agent 认领 dispatch 后如何向 `supervisor` 回写结果

## 1. 流程

1. orchestrator / dispatcher 写入 `codex_agent` dispatch。
2. 目标角色的 Codex agent 认领 dispatch。
3. 对 planning 类任务，agent 回写分析/设计/计划产物。
4. 对 implementation/qa 类任务，agent 回写代码/测试/风险说明。
5. 控制平面继续消费通知并更新 broker、board、PLANS、batch 状态。

## 2. 当前桥接脚本

当前仓库提供桥接器：

- `scripts/ai_team_codex_dispatch_runner.py`

支持命令：

- `claim --role <agent-role>`
- `complete --dispatch-id <dispatch-id>`
- `fail --dispatch-id <dispatch-id> --message <reason>`

## 3. 运行中使用的文件

- dispatch outbox:
  - `docs/ai-team/operations/M1_M2_72H_CODEX_AGENT_DISPATCHES.jsonl`
- notification sink:
  - `docs/ai-team/operations/M1_M2_72H_AGENT_NOTIFICATIONS.jsonl`
- bridge state:
  - `docs/ai-team/operations/M1_M2_72H_CODEX_AGENT_RUNNER_STATE.json`

## 4. v2 完成通知最小格式

```json
{
  "agent_path": "backend-agent",
  "agent_id": "backend-agent",
  "owner_role": "backend-agent",
  "task_id": "INIT-FOO-IMPLEMENT",
  "task_ref": "INIT-FOO-IMPLEMENT",
  "shift_id": null,
  "summary": "initiative implementation",
  "work_order_id": "INIT-FOO-IMPLEMENT#codex#1",
  "emitted_at": "2026-05-25T00:00:00+08:00",
  "status": {
    "completed": "implementation completed"
  },
  "execution": {
    "delivery": {
      "mode": "codex_agent",
      "dispatch_id": "INIT-FOO-IMPLEMENT#codex#1",
      "changed_files": ["scripts/example.py"],
      "artifacts_produced": ["docs/ai-team/operations/init-foo_implementation.json"],
      "tests_run": [
        {"command": "python3 scripts/ai_team_codex_dispatch_runner.py status --json", "status": "passed"}
      ],
      "risk_notes": ["needs final human review before release"],
      "handover_notes": ["qa-agent should verify approved batch output"]
    }
  }
}
```

对 analysis/design/planning 任务，`changed_files` 可以为空，但应至少通过 `artifacts_produced`、`risk_notes`、`handover_notes` 回写规划证据。

## 5. 失败通知最小格式

```json
{
  "agent_path": "frontend-agent",
  "owner_role": "frontend-agent",
  "task_id": "INIT-FOO-IMPLEMENT",
  "work_order_id": "INIT-FOO-IMPLEMENT#codex#1",
  "status": {
    "errored": "frontend contract mismatch"
  },
  "execution": {
    "delivery": {
      "mode": "codex_agent",
      "dispatch_id": "INIT-FOO-IMPLEMENT#codex#1",
      "risk_notes": ["needs backend field alignment"]
    }
  }
}
```

## 6. 设计约束

- 真实 Codex agent 不直接篡改 queue/runtime/broker。
- 所有状态变更仍通过通知消费链完成。
- `dispatch_id` 继续复用 `work_order_id` 字段回写，保持与现有控制平面兼容。
- 对 implementation / qa / compliance / release 类任务，未获批准的 dispatch 不得认领。
- 对 planning 类任务，允许在未批准整体 initiative 时先行回写分析、设计和计划产物。
- 若需要下游角色继续接手，优先通过 `handover_notes` 回写交接摘要。
