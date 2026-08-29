# 0002. 统一分析数据契约与持久化结构

**Date**: 2026-08-29
**Status**: Proposed

## Summary

本规格为 ErgoAgent 规定一套统一的数据结构，覆盖视频、分析任务、分析运行、人员、逐帧观察、风险事件、证据帧、结果文件和组件来源。关系字段使用 SQLite 表和外键，姿态、角度和 REBA 的细节使用经过 Pydantic 校验的 JSON。视频等大文件保存在本地文件系统，数据库只保存元数据和相对路径，所有结果都带 schema、模型、规则和生成时间版本。

## Context

当前脚手架只有一个简单的 `analysis_tasks` 表，任务使用文件名表示输入，尚不能表达视频文件、分析运行、人员轨迹和风险证据之间的关系。后续姿态模型、REBA 规则、风险事件、前端和 Agent 都需要读取同一个结果来源。如果每个模块自行定义 JSON，历史结果会无法复用，风险解释也无法追溯到具体帧和规则。

项目仍以本机单用户和公开视频为目标，数据量以短视频和比赛演示为主。SQLite 适合保存关系、状态和索引，逐帧细节需要保留灵活性，使用 JSON 文本可以先保持模型适配速度。文件内容不适合放进数据库，路径必须限制在数据根目录内，避免路径穿越和日志泄露。

数据需要同时支持强一致的任务状态和可重复的分析结果。任务状态由 API 和 Worker 修改，分析事实只由 Worker 写入，前端和 Agent 只读。失败任务必须留下错误状态，重试不能覆盖原始运行记录。

## Requirements

**User stories**:

- 作为分析人员，我希望上传一个视频并查看任务、分析运行和风险事件的稳定标识，这样我能重复打开同一份结果。
- 作为复核人员，我希望从风险事件追溯到人员、时间、关节、角度、规则、模型和证据帧，这样我能判断结论是否可信。
- 作为前端和 Agent 开发者，我希望使用统一 JSON 和分页接口读取结果，这样不需要重新解析视频或猜测字段。

**Acceptance criteria**:

- **AC-1**：上传的视频资产保存原始文件名、媒体类型、大小、校验值、媒体信息和数据根目录内的相对路径，数据库不保存视频二进制内容或绝对路径。
- **AC-2**：分析任务和分析运行都有持久化状态，状态只能按规定的转换变化，Worker 中断后不会留下无法识别的状态，重试会生成新的运行记录。
- **AC-3**：每次成功或失败的分析运行都保存输入视频标识、结果 schema 版本、模型版本、规则版本、组件来源和生成时间。
- **AC-4**：逐帧观察以 `run_id、worker_id、frame_index` 唯一定位，包含时间戳、边界框、二维姿态、可选三维姿态、关键点置信度、关节角度和 REBA 细节。
- **AC-5**：风险事件必须关联分析运行和人员，包含起止帧与时间、峰值和平均分、身体部位、重复次数、置信度以及至少一帧证据。
- **AC-6**：视频、任务、人员、风险事件和证据读取接口返回稳定的 Pydantic JSON，列表接口支持 `limit` 和 `cursor`，无效标识、状态和参数返回一致错误结构。
- **AC-7**：文件写入使用临时文件和原子替换，路径只能解析到数据根目录，默认不记录原始视频内容；超过大小、类型或时长限制的输入会在任务创建前失败。
- **AC-8**：Alembic 迁移可以在空 SQLite 数据库中建立全部表、外键、唯一约束和索引，并能通过实际查询确认结构已经生效。

## Options considered

### Option 1: 关系型核心加受控 JSON 细节

用关系表保存实体、状态、外键和查询索引，用 JSON 保存姿态、角度、REBA 和模型输出的细节，并由 Pydantic 在写入和读取时校验。`(basis: 现有 SQLite、SQLAlchemy 和 Pydantic 技术栈；关系数据建模实践)`

**Pros**:

 关系约束清晰，能按人员和时间查询风险，模型字段变化不会频繁改表，未来可迁移到 PostgreSQL。

**Cons**:

 JSON 内部字段不能完全由数据库约束，复杂统计需要在应用层解析或补充专用列。

### Option 2: 全部结果存为版本化 JSON 文件

每次分析只写一个或少数几个 JSON 文件，数据库只保存任务状态和文件路径，读取时加载整个结果文件。`(basis: 文件优先原型实践)`

**Pros**:

 写入逻辑简单，容易复制完整结果，也不需要为每个姿态字段设计列。

**Cons**:

 多人员和时间范围查询必须加载大文件，无法可靠建立外键和分页，前端与 Agent 的查询延迟会随视频长度增长。

### Option 3: 引入专用时序或文档数据库

使用专用时序数据库或文档数据库保存逐帧数据，关系数据库只保存任务和文件元数据。`(basis: 高吞吐时序系统实践)`

**Pros**:

 适合极高帧率和长时间数据写入，可使用专门的时间范围查询能力。

**Cons**:

 当前没有测量到的写入瓶颈，增加服务、备份和部署依赖会削弱本地比赛复现能力。

## Decision

**Chosen option**: Option 1: 关系型核心加受控 JSON 细节。

以 SQLite 和 SQLAlchemy 保存关系实体、状态和索引，以 Pydantic 模型定义 JSON 细节，使用 Alembic 管理迁移。视频、结果视频、报告和证据帧只保存到 `ERGOAGENT_DATA_ROOT` 下的固定目录，数据库保存相对路径和校验值。

## Rationale

ErgoAgent 的核心查询是关系型的，例如某次运行中的人员、某个人员的风险事件、某个事件的证据帧和某一帧的角度。关系表可以用外键和唯一约束保护这些关系，SQLite 又能满足当前单机规模。姿态模型的关键点和规则细节会随模型适配变化，受 Pydantic 校验的 JSON 比把所有细节硬编码为列更适合第一阶段。(basis: `docs/specs/0001-stack-and-architecture.md`、`docs/architecture/overview.md`、关系数据库和 schema versioning 实践)

全 JSON 文件方案虽然容易开始，但会让时间范围查询、分页和 Agent 工具都依赖加载完整文件。专用数据库的收益要等真实写入指标证明后再考虑。当前方案把稳定查询字段放进关系表，把变化快的模型细节放进 JSON，同时保留结果文件用于完整复核和导出。(basis: SQLite、SQLAlchemy、Alembic 和 Pydantic 官方文档)

## Feature design

**Data model sketch**:

| Entity | Key fields | Relationships and constraints |
|---|---|---|
| `video_assets` | `id` UUID，`original_name` 必填，`storage_path` 必填，`sha256` 必填，`size_bytes` 必填，`mime_type` 必填，`duration_ms`、`width`、`height`、`fps` 可空，`created_at` 必填 | `sha256` 建索引，`storage_path` 唯一；只保存相对路径 |
| `analysis_tasks` | `id` UUID，`video_asset_id` 必填，`status` 必填，`requested_at`、`started_at`、`finished_at` 可空，`error_code`、`error_message`、`cancel_requested_at` 可空，`lease_owner`、`lease_expires_at` 可空 | `video_asset_id` 外键到 `video_assets`；状态为 `queued`、`running`、`succeeded`、`failed`、`cancelled`；运行中的任务必须有未过期租约 |
| `analysis_runs` | `id` UUID，`task_id` 必填，`attempt` 必填，`status` 必填，`started_at`、`finished_at`、`error_code`、`error_message` 可空，`schema_version`、`ruleset_version` 必填，`model_summary` JSON 必填，`generated_at` 必填 | `task_id` 外键到 `analysis_tasks`；一个任务可有多个运行；`(task_id, attempt)` 唯一 |
| `run_components` | `id` UUID，`run_id` 必填，`name`、`version`、`source_url`、`license` 必填，`weight_uri`、`weight_sha256` 可空 | `run_id` 外键到 `analysis_runs`；`(run_id, name, version)` 唯一 |
| `workers` | `id` UUID，`run_id` 必填，`source_track_id` 必填，`first_frame`、`last_frame`、`confidence` 必填 | `run_id` 外键到 `analysis_runs`；`(run_id, source_track_id)` 唯一 |
| `frame_observations` | `run_id`、`worker_id`、`frame_index` 必填，`timestamp_ms`、`bbox`、`pose_2d`、`confidence`、`angles`、`reba` 必填，`pose_3d` 可空 | 复合主键 `(run_id, worker_id, frame_index)`；`worker_id` 外键到 `workers`；按 `(run_id, timestamp_ms)` 建索引 |
| `risk_events` | `id` UUID，`run_id`、`worker_id` 必填，`start_frame`、`end_frame`、`start_ms`、`end_ms`、`peak_score`、`mean_score`、`body_region`、`repetition_count`、`confidence` 必填 | 外键到运行和人员；`end_frame >= start_frame`、`end_ms >= start_ms`；按运行、人员和开始时间建索引 |
| `evidence_frames` | `id` UUID，`run_id`、`event_id`、`worker_id`、`frame_index` 必填，`storage_path`、`sha256`、`reason` 必填 | 外键到事件和人员；`(event_id, frame_index)` 唯一；路径只能位于证据目录 |
| `result_artifacts` | `id` UUID，`run_id` 必填，`kind`、`storage_path`、`sha256`、`size_bytes`、`mime_type` 必填 | `kind` 在同一运行内唯一；支持 `result_json`、`annotated_video`、`report` |

JSON 字段使用明确的 Pydantic 类型。`pose_2d` 和 `pose_3d` 的关键点名称、坐标单位、置信度范围在数据契约模块中固定，`angles` 使用角度值和关节名称，`reba` 保存分项分数、总分、风险等级和规则解释。任何 JSON 增字段必须提升 `schema_version` 或保持向后兼容。

第一版 JSON 形状固定如下：`pose_2d` 使用原始视频帧像素坐标，包含 `format`、`coordinate_space`、`frame_width`、`frame_height` 和按规范关键点名称索引的 `keypoints`，每个关键点包含 `x`、`y`、`confidence`。`pose_3d` 可空，存在时包含 `format`、`coordinate_space`、`unit` 和带 `x`、`y`、`z`、`confidence` 的关键点。`angles` 使用角度名称索引，每项包含 `degrees`、`confidence` 和来源关键点。`reba` 包含 `score`（1 到 15 的整数）、`risk_level`（`negligible`、`low`、`medium`、`high`、`very_high`）、分项分数和 `rule_version`。缺失或遮挡的值使用显式 `null`，不使用零代替未知。

**State transitions**:

```text
analysis_task: queued → running → succeeded
                            └────→ failed
                            └────→ cancelled
failed: retry creates a new analysis_run, task remains an immutable record
```

`queued → running` 只能由 Worker 以租约方式领取，`running → succeeded` 或 `failed` 只能由同一运行的 Worker 写入。取消请求只能把 `queued` 任务变为 `cancelled`，运行中的任务先写入 `cancel_requested_at`，再由 Worker 收尾为 `cancelled` 或 `failed`。租约包含 `lease_owner` 和 `lease_expires_at`，过期租约可以被其他 Worker 重新领取。任务和运行的状态变更与时间字段在同一事务中提交。

**API surface**:

| Endpoint | Method | Key inputs | Key outputs | Auth | Key errors |
|---|---|---|---|---|---|
| `/api/videos` | POST | `file` multipart，必填；`Idempotency-Key` 可选 | `video_asset_id`、媒体元数据、存储状态 | 本机访问 | 400 类型不支持，413 超限，409 校验值重复 |
| `/api/analysis-tasks` | POST | `video_asset_id` 必填，`profile` 可选 | `task_id`、`status`、`requested_at` | 本机访问 | 404 视频不存在，409 视频正在分析，422 参数无效 |
| `/api/videos/{video_id}` | GET | 路径中的 `video_id` | 视频元数据、校验值、可用结果数量 | 本机访问 | 404 不存在 |
| `/api/analysis-tasks/{task_id}` | GET | 路径中的 `task_id` | 任务状态、运行编号、错误信息 | 本机访问 | 404 不存在 |
| `/api/analysis-runs/{run_id}` | GET | 路径中的 `run_id` | 输入、版本、运行状态、组件和结果文件 | 本机访问 | 404 不存在，409 结果未完成 |
| `/api/analysis-runs/{run_id}/workers` | GET | `limit` 1 到 100，`cursor` 可选 | 人员摘要列表、下一页游标 | 本机访问 | 404 运行不存在，422 游标无效 |
| `/api/analysis-runs/{run_id}/risk-events` | GET | `worker_id` 可选，`limit` 1 到 100，`cursor` 可选 | 风险事件列表、下一页游标 | 本机访问 | 404 运行不存在，422 参数无效 |
| `/api/risk-events/{event_id}` | GET | 路径中的 `event_id` | 风险事件、规则细节、证据帧元数据 | 本机访问 | 404 不存在，409 运行未完成 |
| `/api/evidence-frames/{evidence_id}/content` | GET | 路径中的 `evidence_id` | 图片二进制和安全的媒体类型 | 本机访问 | 404 不存在，410 文件已清理 |

所有错误返回统一结构：`{"error":{"code":"...","message":"...","details":{}}}`。分页游标由服务端生成，排序固定为主键和时间的组合，不接受客户端拼接 SQL。

**Value sourcing**:

| Action | Value produced / displayed | Source |
|---|---|---|
| 上传视频 | 原始名称、大小、类型、校验值、媒体信息 | multipart 文件内容、FFprobe 解析结果、`video_assets` 列 |
| 创建任务 | 任务编号、状态、请求时间 | `analysis_tasks.id`、状态机初始值 `queued`、服务器 UTC 时间 |
| 查询任务 | 运行编号、完成时间、错误信息 | `analysis_tasks` 与其最新 `analysis_runs` 的列 |
| 查询运行 | schema、模型、规则、生成时间、结果文件 | `analysis_runs`、`run_components`、`result_artifacts` |
| 查询人员 | Worker ID、首末帧、置信度、暴露摘要 | `workers` 列和同一运行的 `frame_observations` 聚合 |
| 查询风险事件 | 起止时间、峰值、平均分、身体部位、重复次数、置信度 | `risk_events` 列，时间由 `frame_observations.timestamp_ms` 聚合确认 |
| 查询事件证据 | 证据编号、帧号、原因、图片内容 | `evidence_frames` 列和数据根目录内的 `storage_path` |
| Agent 读取事实 | 结构化事实和来源位置 | 上述只读 API 或内部 service，禁止从原始视频推断 |

**Key invariants**:

1. 所有 UUID、时间和版本字段由服务端生成或由已登记的组件清单提供，客户端不能覆盖。
2. 所有外键启用约束，删除视频或运行前必须先检查引用；第一阶段不提供级联删除 API。
3. 一个逐帧观察只能属于一个运行、一个人员和一个帧号组合。
4. 风险事件的结束位置不早于开始位置，证据帧必须属于同一运行和人员。
5. 成功运行必须至少有一个 `result_json` 文件，文件校验值与数据库一致；文件未完整写入时运行不能成功。
6. 结果事实写入后不可由 API 或 Agent 修改。重新分析必须创建新的任务和运行。
7. 所有服务端时间使用 UTC ISO 8601，前端本地化只发生在展示层。
8. 数据库内的路径必须是相对 POSIX 路径，解析后的真实路径必须仍位于配置的数据根目录。

**Migration strategy**:

仓库尚未进入生产阶段，当前 `data/ergoagent.db` 是可删除的开发产物。Alembic 首个正式迁移从空数据库建立上述结构，并检测脚手架旧表的 `source_name` 字段，发现旧数据时给出明确错误而不做猜测性转换。开发者可以在迁移前删除该本地数据库；未来有真实数据时必须另立迁移规格并设计回填。

**Security model**:

第一阶段只允许本机回环地址访问，不区分账号。API 允许创建视频和任务，Worker 允许写入分析事实，前端和 Agent 只允许读取已完成运行。原始视频、证据图片和报告属于敏感作业资料，不写入日志，不上传模型服务，不在错误响应中返回内容。外部部署前必须另立认证、权限、传输加密、审计日志和数据保留规格；不能把当前本机模式直接暴露到公网。

**Configuration required**:

- `ERGOAGENT_DATA_ROOT`：视频、结果、证据和报告的根目录，默认 `./data`。
- `ERGOAGENT_MAX_UPLOAD_BYTES`：单个上传文件大小上限，默认 2 GiB。
- `ERGOAGENT_MAX_VIDEO_DURATION_SECONDS`：视频时长上限，默认 1800 秒。
- `ERGOAGENT_RETENTION_DAYS`：本地文件自动清理天数，默认 30 天；第一阶段只记录配置，不自动删除未完成任务文件。

**Critical test scenarios**:

- Happy path：上传视频、创建任务、Worker 完成运行、查询人员和风险事件并读取证据帧，验证 **AC-1**、**AC-2**、**AC-3**、**AC-4**、**AC-5**、**AC-6**。
- Failure case：上传超限文件、Worker 中断和结果文件校验值不一致，确认任务失败、错误结构稳定且不会产生成功运行，验证 **AC-2**、**AC-7**。
- Auth/permission：本机以外的请求被部署配置拒绝，Agent 尝试写入事实接口返回拒绝，验证 **AC-6**、**AC-7**。
- Migration：在空 SQLite 数据库执行 Alembic 迁移并查询所有表、外键、唯一约束和索引，验证 **AC-8**。

## Build plan

本功能沿用项目的垂直切片方法。先建立可查询的关系结构，再接入文件边界、任务状态和结果读取，最后用真实迁移和失败场景验证整条链路。

1. 创建 SQLAlchemy 模型和 Alembic 初始迁移，建立视频、任务、运行、人员、逐帧、事件、证据、结果文件和组件表，满足 **AC-1**、**AC-2**、**AC-3**、**AC-4**、**AC-5**、**AC-8**。
2. 实现本地文件存储服务，完成上传校验、相对路径、SHA256、临时文件和原子替换，满足 **AC-1**、**AC-7**。
3. 实现任务和运行状态服务，加入 Worker 租约、合法状态转换、失败记录和重试新运行，满足 **AC-2**、**AC-7**。
4. 实现 Pydantic 数据契约和结果封装，校验逐帧 JSON、REBA 细节、版本字段、组件来源和结果文件清单，满足 **AC-3**、**AC-4**、**AC-5**。
5. 实现任务、运行、人员、风险事件和证据读取接口，统一错误结构和游标分页，满足 **AC-5**、**AC-6**。
6. 在临时 SQLite 数据库应用迁移，运行完整测试、路径安全测试、失败恢复测试和接口测试，确认实际 schema 与契约一致，满足 **AC-6**、**AC-7**、**AC-8**。

## Consequences

**Positive**:

1. 前端、报告和 Agent 可以共享同一套结果来源，不需要重复解析视频。
2. 风险结论可以定位到运行、人员、帧、规则和证据文件，便于比赛演示和人工复核。
3. SQLite 和本地文件保持安装简单，未来可以在不改变 JSON 契约的前提下迁移到 PostgreSQL 和对象存储。
4. 失败运行和组件来源被保留，实验结果不会被重试覆盖。

**Negative / tradeoffs**:

1. 逐帧关系记录会随着视频长度增长，SQLite 不适合未经测量的高并发或超长视频。
2. JSON 细节的数据库约束较弱，必须依赖 Pydantic、版本字段和测试。
3. 文件校验、清理和数据库事务需要协调，写入流程比单个 JSON 文件更复杂。
4. 现有脚手架的 `source_name` 任务字段不再是正式契约，开发阶段需要迁移或重建本地数据库。

**Neutral**:

1. 第一阶段不提供级联删除和公网访问，数据清理作为独立运维任务推进。
2. 复杂统计先使用应用层聚合，测量到性能问题后再增加物化摘要或专用存储。

## Follow-up

- [ ] 由 `/develop data contract and persistence` 实现模型、迁移、文件服务、契约和读取接口。
- [ ] 为 `pose_2d`、`pose_3d`、`angles` 和 `reba` 编写独立 Pydantic schema，并与实际模型输出逐项核对。
- [ ] 明确 REBA 风险等级、身体部位枚举和重复次数算法来源，写入规则规格而不是在数据层猜测。
- [ ] 在实现前决定本地开发数据库的迁移策略，默认允许删除脚手架阶段的临时 `data/ergoagent.db`。
- [ ] 完成数据层后运行 `/check verify data contract and persistence` 和 `/test data contract and persistence`。
- [ ] 外部部署前补充认证、数据保留和审计日志规格。

## References

**Project sources**:

- `docs/specs/0001-stack-and-architecture.md`，SQLite、本地文件、Worker 和版本化结果边界
- `docs/architecture/overview.md`，统一结果契约和模块边界
- `docs/scope/scope.md`，数据契约与持久化功能的范围和验收方向
- `backend/app/db.py`，当前脚手架任务表，需要由本规格替换为正式模型
- `agent.md`，证据链、许可证和长期维护约定

**Practices & standards**:

- 数据库迁移必须应用到目标数据库并通过实际 schema 查询确认
- 外键、唯一约束和状态机在数据库与应用层双重保护
- 大文件保存文件系统或对象存储，数据库保存元数据和校验值
- Pydantic schema versioning，结果字段变更必须可追溯
- 原子文件写入和结构化错误响应

**Links** (web verified on 2026-08-29):

- SQLite documentation: https://www.sqlite.org/docs.html
- SQLAlchemy documentation: https://docs.sqlalchemy.org/
- Alembic documentation: https://alembic.sqlalchemy.org/
- Pydantic documentation: https://docs.pydantic.dev/
- FastAPI documentation: https://fastapi.tiangolo.com/
