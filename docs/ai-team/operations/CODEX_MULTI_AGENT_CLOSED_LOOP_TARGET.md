# Codex 多 Agent 全自动闭环研发目标架构

- 更新时间：`2026-04-05 22:20 +08:00`
- 适用范围：`kernel-sense` 仓库内 `ai-team` / `Codex` 迁移与后续架构演进
- 当前判断：仓库内现有 `ai-team` 主要是“脚本化自动化控制平面”，还不是“由真实 Codex agent 组成的研发团队”

## 1. 文档目的

本文件用于纠偏 `ai-team` 的目标定义，避免继续把“固定命令自动执行”误判为“多 Agent 全自动闭环研发”。

本文件之后的统一口径：

- 当前 `supervisor + agent_runner + monitor + automations` 是过渡期控制平面
- 目标形态应是“真实 Codex agent team”
- 控制平面继续保留，但降级为调度、审计、门禁、回写基础设施

## 2. 目标定义

本项目要实现的 `ai-team`，应满足以下条件：

1. `orchestrator` 能把用户需求拆解为父子任务和依赖图。
2. 每个领域角色都对应真实 Codex agent，而不是逻辑占位角色。
3. 各 agent 按授权目录和任务边界并行产出真实代码、测试、文档和风险说明。
4. `orchestrator` 能自动汇总子任务交付物并完成集成。
5. 集成后自动执行测试、合规、接口、环境和发布门禁。
6. 低风险链路可无人值守闭环，高风险链路必须进入人工审批。

如果上述第 2、3、4 步未成立，就不能称为“多 Agent 全自动闭环研发项目”。

## 3. 当前状态与目标状态的差异

### 3.1 当前状态

当前仓库内已落地能力主要包括：

- `plan -> queue -> work_order -> notification -> runtime` 状态链路
- 基于 `executor_rule` 的固定命令和受控执行器调度
- 文件锁、班次、Gate、重试、自愈、GitLab 轮询与 follow-up
- monitor、runtime、broker、jsonl 工单流的运行态观测

这些能力说明当前系统已经具备“自动化执行与状态闭环”能力，但核心仍是：

- 自动执行预定义命令
- 自动刷新报告
- 自动回写状态
- 自动探测远端环境

这不是目标中的“真实多 Agent 编码协作”。

### 3.2 目标状态

目标状态应改为：

- `orchestrator` 派发的是“任务卡 + 写入边界 + 验收标准”
- `backend/frontend/probe/compliance/qa/devops-agent` 由真实 Codex agent 执行
- 子 agent 返回的是“代码补丁 + 测试结果 + 风险说明 + 交接摘要”
- 控制平面负责调度、锁、回写、验收、发布 Gate
- 发布链保留审批和回滚策略

## 4. 目标架构

### 4.1 控制平面

控制平面继续保留，职责收敛为：

- 读取 `PLANS.md`、`AGENTS.md`、任务卡、自动化规则
- 维护任务队列、依赖关系、文件锁、运行态
- 执行门禁、审计、报告汇总、审批流和回滚流

建议控制平面组件：

- `planner`
- `dispatcher`
- `broker`
- `runtime`
- `gatekeeper`
- `release-controller`

### 4.2 执行平面

执行平面是未来真正的 `ai-team` 本体：

- `orchestrator`
- `backend-agent`
- `frontend-agent`
- `probe-agent`
- `compliance-agent`
- `qa-agent`
- `devops-agent`

每个 agent 都必须是实际可工作的 Codex agent，而不是仅在 JSON 里维护一个状态名字。

### 4.3 工具平面

工具平面承接各类受控能力：

- Git / branch / worktree / MR
- API 合同验证
- 浏览器 E2E
- 数据库迁移与回归
- 远端环境验证
- 发布与回滚

这些能力仍应通过受控执行器暴露，避免执行平面无限制自由 shell。

## 5. 统一任务协议

后续所有 `ai-team` 任务应统一为结构化协议，而不是临时 shell 命令。

建议任务输入字段：

- `task_id`
- `parent_task_id`
- `owner_role`
- `collaborators`
- `goal`
- `constraints`
- `write_scopes`
- `read_scopes`
- `artifacts`
- `acceptance_commands`
- `risk_notes_required`
- `rollback_hint`

建议任务输出字段：

- `status`
- `changed_files`
- `patch_summary`
- `tests_run`
- `artifacts_produced`
- `risk_notes`
- `handover_notes`
- `followups`

## 6. Agent 交付协议

每个真实 Codex agent 的最小交付物必须一致：

- 变更文件列表
- 关键实现摘要
- 已执行测试和结果
- 风险说明
- 需要上游或下游继续处理的 follow-up

建议标准化为：

```json
{
  "task_id": "TASK-XXX",
  "owner_role": "backend-agent",
  "status": "completed",
  "changed_files": ["backend/app/..."],
  "tests_run": [
    {"command": "pytest ...", "status": "passed"}
  ],
  "artifacts_produced": ["docs/..."],
  "risk_notes": ["..."],
  "handover_notes": ["..."]
}
```

## 7. 自动闭环的正确边界

### 7.1 可自动闭环

- 任务拆解和派发
- 低风险代码实现
- 测试与文档补齐
- API/UI/合规/环境验证
- 集成分支合并
- 预发布环境部署与验活

### 7.2 保留审批

- 生产发布
- 高风险 schema 变更
- 密钥轮换
- 越权目录改动
- 合规例外放行

## 8. 从当前仓库到目标形态的改造顺序

### 阶段 A：控制平面去“伪 agent 化”

目标：承认当前 `agent_runner` 是自动化执行器，不再把它视为真实研发 agent。

本阶段动作：

- 保留 `supervisor / broker / runtime / monitor`
- 明确 `agent_runner` 仅负责受控执行器和固定命令
- 文档统一改口径，不再把现状描述为“全自动研发团队”

### 阶段 B：接入真实 Codex 执行平面

目标：让 `orchestrator` 真正调度 Codex agent 干活。

本阶段动作：

- 引入真实 Codex agent 调度入口
- 从“下发 shell 命令”改为“下发任务协议”
- 每个 agent 在独立工作区内完成交付
- 回写统一结构化交付结果

### 阶段 C：补 Git 闭环

目标：让代码交付进入真正的工程集成路径。

本阶段动作：

- 自动创建 branch / worktree
- 自动提交 patch
- 自动生成 MR
- 增加 reviewer gate
- 低风险任务允许自动 merge 到集成分支

### 阶段 D：补验证与发布闭环

目标：把“代码完成”推进到“环境可验收”。

本阶段动作：

- 接入 API 合同验证
- 接入浏览器 E2E
- 接入数据库迁移执行器
- 接入 staging 发布、验活、失败回滚

### 阶段 E：形成项目级闭环

目标：实现“需求 -> 拆解 -> 实现 -> 验证 -> 集成 -> 预发布”的完整链路。

完成判定：

- 控制平面负责调度与门禁
- 执行平面由真实 Codex agent 构成
- 大部分研发任务可自动推进到 staging ready
- 人工只在高风险审批和例外处置介入

## 9. 当前仓库的近期改造优先级

优先级建议如下：

1. 把 `ai-team` 的口径从“自动化闭环处置”与“Codex 多 Agent 研发闭环”拆开
2. 给 `orchestrator` 增加真实 Codex agent 派发协议
3. 给各角色增加统一交付协议和工作区隔离
4. 给控制平面补 Git / MR / reviewer gate
5. 给验证链补 browser/db/release 受控执行器

## 10. 一句话结论

当前仓库内的 `ai-team` 不是最终目标中的“Codex 多 Agent 研发团队”，而是该团队未来要依赖的控制平面。

后续所有架构、文档和实现都应围绕这个判断推进，避免继续把“脚本化自动执行”当作“真实多 Agent 研发闭环”。
