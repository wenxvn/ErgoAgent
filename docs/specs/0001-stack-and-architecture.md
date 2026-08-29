# 0001. 采用模块化单体技术栈与本地优先架构

**Date**: 2026-08-29
**Status**: Proposed

## Summary

ErgoAgent 采用模块化单体架构，也就是一个可以独立启动的应用，内部按模块分工。后端和视觉分析使用 Python，前端使用 React 和 Vite，任务状态保存在 SQLite，视频和证据帧保存在本地文件中。长时间的视频分析由独立 Worker 处理，网页请求只负责创建任务和读取结果。

## Context

ErgoAgent 当前是绿色项目，没有业务代码和既有工程清单。第一阶段的目标是单机离线演示，输入公开视频，完成姿态分析、关节角度、REBA 风险、证据链和结果展示。团队规模和用户规模都很小，最重要的约束是尽快得到可重复的真实结果，同时让比赛演示、后续维护和问题定位都足够简单。

视频分析包含模型推理、文件处理和连续任务，通常会运行数秒到数分钟。它不能占用网页请求线程，也不能只保存在内存中，否则进程重启后无法知道任务状态。分析结果包含人员、帧、角度、规则和证据之间的关系，必须能按版本追溯，不能把原始视频塞进数据库。

> ⚠️ Premise note: 主题同时涉及技术栈、任务执行、文件存储、数据版本和 Agent 边界。为避免一次引入过多独立决策，本规格只固定基础架构和运行边界。数据契约、界面基础、视频分析链路和 Agent 工具协议将在后续规格中分别确认。

## Requirements

本架构必须满足以下约束：

1. **R-1**：项目能够在一台普通开发机上以本地模式启动，核心分析不依赖云端密钥。
2. **R-2**：API 不能在请求线程执行 GPU 推理。长任务必须写入数据库任务表，由独立 Worker 领取并更新状态。
3. **R-3**：视频、结果视频、证据帧和报告使用文件系统保存，数据库只保存路径、校验值、大小、媒体信息和业务元数据。
4. **R-4**：分析结果必须带有输入标识、结果 schema 版本、模型版本、规则版本和生成时间。
5. **R-5**：前端只展示 API 返回的事实，不自行计算姿态、角度或风险分数。
6. **R-6**：Agent 只能调用已注册的分析工具读取结构化证据，不能修改原始分析事实，也不能在没有证据时生成确定性风险结论。
7. **R-7**：默认部署为本机单用户。任何外部访问、多人使用或敏感视频场景，都必须先增加认证、访问控制、传输保护和更严格的数据保留策略。
8. **R-8**：组件和模型接入前必须记录来源、版本、许可证、权重来源和本项目改动。

## Options considered

### Option 1: Python 与 TypeScript 的模块化单体

使用一个 Python 后端和独立的 React 前端，视觉分析、API 和 Worker 在同一个仓库中按模块组织，使用 Docker Compose 统一启动。`(basis: docs/scope/scope.md 中的垂直切片和单机演示约束；模块化单体实践)`

**Pros**:

 便于共享数据契约，调试路径短，部署组件少，适合一到五人的小团队。

**Cons**:

 后端进程和 Worker 仍需分别运行，模块边界主要靠代码规范维护，未来扩展到多人协作时需要补充隔离能力。

### Option 2: 多服务架构

把视频处理、姿态推理、规则计算、Agent 和网页接口拆成多个服务，通过消息队列和网络接口连接。`(basis: 分布式服务实践)`

**Pros**:

 可以独立扩展 GPU 推理，也可以让不同团队分别维护服务。

**Cons**:

 需要服务发现、队列、部署编排、跨服务追踪和更多故障处理。当前没有已测量的吞吐瓶颈，额外复杂度会直接挤压比赛版本的实现时间。

### Option 3: 单进程 Python 原型

使用一个 Python 进程同时提供页面、接口和分析，页面可用简单的 Python UI 框架生成。`(basis: 快速原型实践)`

**Pros**:

 初始文件少，启动命令简单，适合验证一张图片或一段很短的视频。

**Cons**:

 长任务、前端交互、任务恢复和浏览器体验很快会互相牵制。后续加入结果时间轴、证据帧和 Agent 追问时容易重写。

## Decision

**Chosen option**: Option 1: Python 与 TypeScript 的模块化单体。

ErgoAgent 使用单仓库、模块化单体和独立 Worker。第一阶段默认本地单用户，第二阶段再在不改变核心数据契约的前提下增加网页能力和受约束的 Agent。

## Rationale

当前没有生产流量、没有多团队边界，也没有经过测量的性能瓶颈。模块化单体可以保留清晰的控制器、服务、分析核心和存储边界，同时只需要一套仓库和少量进程。它最符合当前的垂直切片方法，能先完成真实的视频到结果链路，再逐步增加功能。(basis: `docs/scope/scope.md`、`docs/architecture/overview.md`、Tracer Bullet 和模块化单体实践)

Python 直接连接 PyTorch、OpenCV、FFmpeg 和现有姿态项目，能减少模型适配成本。React 和 Vite 适合构建可扫描的结果工作台，前端不承担分析逻辑。SQLite 和本地文件系统满足单机演示的可靠性与可恢复性，也为后续迁移到 PostgreSQL 和对象存储保留清晰边界。多服务架构和单进程原型都可以在未来用于特定场景，但现在分别会带来过高的运维成本或过早的重写风险。(basis: REBAPose、MotionBERT 官方项目；Python、PyTorch、React 和 SQLite 官方文档)

## Proposed stack

| Layer | Choice | Reason |
|---|---|---|
| Architecture | 模块化单体，API 与 Worker 分进程 | 进程边界隔离长任务，代码仍保持单仓库和共享契约 |
| Language | Python 3.11 或更高版本，TypeScript | Python 连接视觉生态，TypeScript 约束前端数据结构 |
| Backend framework | FastAPI，Pydantic | 提供清晰的 REST JSON 接口和可验证的请求响应模型 |
| Frontend | React，Vite | 适合结果工作台，开发启动快，构建产物简单 |
| Primary database | SQLite，通过 SQLAlchemy 和 Alembic | 本地零配置，支持关系约束、迁移和后续数据库替换 |
| Task execution | SQLite 任务表加独立 Python Worker | 不新增消息中间件，能够持久化排队、运行、成功和失败状态 |
| File storage | 本地文件系统 | 大文件不进入数据库，证据帧和报告可直接复核 |
| Video processing | FFmpeg，OpenCV | 处理转码、抽帧、媒体信息和结果视频 |
| Vision inference | PyTorch，优先验证 REBAPose 和 MotionBERT | 复用公开权重，先做可解释和可复现的分析链路 |
| Agent integration | 最小工具注册加状态机，通过 OpenAI 兼容接口接入模型 | 让模型负责规划和解释，基础事实仍由确定性工具提供 |
| API protocol | REST JSON，任务状态轮询 | 浏览器和脚本都易于调用，避免第一阶段维护 WebSocket |
| Deployment | Docker Compose，本地默认绑定回环地址 | 比赛现场可以一条命令复现，默认不暴露公网 |
| Observability | 结构化日志，错误追踪作为可选配置 | 记录任务、模型、规则、耗时和错误，避免记录原始视频内容 |
| Authentication | 第一阶段无账号，仅本机访问 | 与单用户演示一致，外部部署前必须另立认证规格 |

### 模块边界

```text
Web UI
  ↓ REST JSON
FastAPI API
  ├── 任务服务，只创建和查询任务
  ├── 结果服务，只读取结构化结果
  └── Agent 服务，只能调用注册工具

Worker
  ├── 媒体处理
  ├── 人员检测与跟踪
  ├── 姿态和三维运动表示
  ├── 角度与 REBA 规则
  ├── 风险事件聚合
  └── 证据与报告生成

SQLite 元数据与任务状态
本地文件系统中的视频、结果、证据和报告
```

### 架构不变量

1. API 进程只做校验、任务编排和结果读取，不执行 GPU 推理。
2. Worker 领取任务时必须使用可恢复的状态转换，进程中断后任务可以标记失败或重新运行。
3. 结果写入采用临时文件加原子替换，数据库记录只有在文件完整后才进入成功状态。
4. 每个事实结果都包含 schema、模型、规则和生成时间版本。
5. Agent 工具返回结构化事实和证据位置，Agent 不得修改结果表。
6. 本地核心分析在没有模型服务密钥时仍能运行，只有自然语言解释可以降级或跳过。
7. 原始视频默认不写入日志，不随 API 错误返回，不上传第三方服务。

## Consequences

**Positive**:

1. 开发者可以用一套仓库理解从视频到报告的完整链路。
2. Worker 进程隔离了 GPU 和长时间任务，网页接口保持可响应。
3. SQLite 和本地文件让比赛现场容易安装、备份和复现。
4. 明确的版本字段和工具边界有利于审查证据链，也降低 Agent 编造事实的风险。

**Negative / tradeoffs**:

1. SQLite 任务表不适合高并发和多机调度，未来扩展需要迁移数据库和队列。
2. 本地文件系统没有对象存储的高可用和跨机器访问能力，必须提供磁盘空间检查和清理策略。
3. Python 与 TypeScript 需要维护接口契约和两套依赖环境。
4. 默认无认证只能用于本机演示，不能直接作为公开服务。

**Neutral**:

1. 未来可以把 Worker 单独部署到 GPU 主机，API 和前端仍沿用 REST 契约。
2. 当出现明确的吞吐、团队 ownership 或数据隔离需求时，可以单独提出迁移规格，而不是预先拆分所有模块。

## Follow-up

- [ ] 依据本规格执行工程骨架，固定 Python、Node、PyTorch 和 FFmpeg 的实际版本，并补充可执行的启动命令。
- [ ] 设计数据契约和持久化规格，明确任务表、视频元数据、逐帧结果、RiskEvent 和证据帧字段。
- [ ] 设计界面基础规格，明确上传、处理中、失败、空结果和低置信度状态。
- [ ] 设计最小视频分析规格，验证 REBAPose、MotionBERT 和本地模型权重的实际运行条件。
- [ ] 在实现后执行构建、运行、接口和测试验证，再把本规格状态推进为 `Accepted`。
- [ ] 外部部署前补充认证、权限、数据保留、传输保护和审计日志规格。
- [ ] 可选安装 FastAPI、React、PyTorch 和 SQLite 的社区 Agent Skill，安装前逐项确认来源和适用范围。

## References

**Project sources**:

- `agent.md`，项目边界、证据链和长期维护约定
- `docs/scope/scope.md`，垂直切片方法、阶段范围和验收方向
- `docs/architecture/overview.md`，模块边界、结果契约和当前状态
- `docs/research/2026-08-29-competition-and-open-source.md`，开源项目和许可证核验记录

**Practices & standards**:

- 模块化单体优先，只有在测量到瓶颈或出现明确 ownership 边界时才拆分服务
- 关系数据库保存关系和状态，大文件保存在文件系统或对象存储
- 后台任务持久化状态，API 请求不执行长时间计算
- 结构化日志和最小权限原则
- Agent grounding，模型只能解释已取得的结构化证据

**Links** (web verified on 2026-08-29):

- FastAPI documentation: https://fastapi.tiangolo.com/
- Python: https://www.python.org/
- React documentation: https://react.dev/
- Vite guide: https://vite.dev/guide/
- SQLite documentation: https://www.sqlite.org/docs.html
- SQLAlchemy documentation: https://docs.sqlalchemy.org/
- Alembic documentation: https://alembic.sqlalchemy.org/
- PyTorch documentation: https://pytorch.org/docs/stable/
- Docker Compose source repository: https://github.com/docker/compose
- FFmpeg documentation: https://ffmpeg.org/documentation.html
- REBAPose: https://github.com/umic-iitm/rebapose
- MotionBERT: https://github.com/Walter0807/MotionBERT
