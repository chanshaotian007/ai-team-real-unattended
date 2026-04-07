# Codex Agent Delivery Contract

- 更新时间：`2026-04-05 22:50 +08:00`
- 目的：定义真实 Codex agent 认领 dispatch 后如何向 `supervisor` 回写结果

## 1. 流程

1. `supervisor` 写入 `codex_agent` dispatch。
2. 目标角色的 Codex agent 认领 dispatch。
3. Codex agent 完成任务后，用统一协议回写 `completed` 或 `errored` 通知。
4. `supervisor` 继续沿用现有通知消费链更新 queue、broker、runtime。

## 2. 当前桥接脚本

当前仓库提供最小桥接器：

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

## 4. 完成通知最小格式

```json
{
  "agent_path": "backend-agent",
  "agent_id": "backend-agent",
  "owner_role": "backend-agent",
  "task_id": "PLAN-S03-TASK-BE-RBAC-002-C",
  "task_ref": "TASK-BE-RBAC-002-C",
  "shift_id": "S03",
  "summary": "backend codex task",
  "work_order_id": "PLAN-S03-TASK-BE-RBAC-002-C#codex#1",
  "emitted_at": "2026-04-05T22:50:00+08:00",
  "status": {
    "completed": "backend codex task done"
  },
  "execution": {
    "delivery": {
      "mode": "codex_agent",
      "dispatch_id": "PLAN-S03-TASK-BE-RBAC-002-C#codex#1",
      "changed_files": ["backend/app/core/security.py"],
      "artifacts_produced": ["backend/tests/test_rbac_dependencies.py"],
      "tests_run": [
        {"command": "pytest backend/tests/test_rbac_dependencies.py -q", "status": "passed"}
      ],
      "risk_notes": ["needs final reviewer pass"],
      "handover_notes": ["qa-agent should verify DM8 path"]
    }
  }
}
```

## 5. 失败通知最小格式

```json
{
  "agent_path": "frontend-agent",
  "owner_role": "frontend-agent",
  "task_id": "PLAN-S07-TASK-DASHBOARD-011",
  "work_order_id": "PLAN-S07-TASK-DASHBOARD-011#codex#1",
  "status": {
    "errored": "frontend contract mismatch"
  },
  "execution": {
    "delivery": {
      "mode": "codex_agent",
      "dispatch_id": "PLAN-S07-TASK-DASHBOARD-011#codex#1",
      "risk_notes": ["needs backend field alignment"]
    }
  }
}
```

## 6. 设计约束

- 真实 Codex agent 不直接篡改 queue/runtime/broker。
- 所有状态变更仍通过 `supervisor` 消费通知完成。
- `dispatch_id` 当前复用 `work_order_id` 字段回写，保持与现有控制平面兼容。
- 若需要下游角色继续接手，优先通过 `handover_notes` 回写交接摘要；`supervisor` 会把显式点名角色的交接项投影到 monitor handover board，并同步进目标 agent 的 `pending_tasks` inbox。
- 对 `handover_followup` 任务，`supervisor` 只会接受带最小交付证据的 `completed` 通知：至少 1 条 `tests_run`，且在 `risk_notes_required=true` 时必须附 `risk_notes`；否则会拒收并把该交接任务重新打开。
- handover completion 被拒收后，`FOLLOWUP-HANDOVER-*` 的处置结果会直接作用于控制面：`handover_redispatch_ready:*` 会为原 handover 打开一次性 redispatch override，`handover_review_required:*` 会保持该 handover 为人工审查状态。
