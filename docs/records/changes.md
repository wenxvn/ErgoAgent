# 更新记录

本文件采用追加方式记录每次项目更新。日期使用北京时间。

## 2026 年 8 月 29 日，建立项目上下文

范围：项目文档和协作流程。

改动或发现：

1. 创建中文 `agent.md`，确定 ErgoAgent 为唯一主项目。
2. 从附件聊天记录中整理出比赛边界、技术路线、开源资料候选和分阶段工作流。
3. 创建架构快照、决策记录、问题记录、赛事资料和全局规划文件。
4. 仓库已初始化为 Git 项目，主分支为 `main`。

证据：当前仓库提交 `1afb8cd`，远程为 `https://github.com/wenxvn/ErgoAgent.git`。

验证：已检查提交身份、远程分支和工作区状态。

影响：业务代码尚未开始，下一步必须先核验开源项目和数据入口，再实现 REBAPose 的最小推理路径。

下一步：见 `docs/plan/2026-global-plan.md`。

## 2026 年 8 月 29 日，完成范围分解

范围：产品执行计划和功能范围。

改动或发现：

1. 新建 `docs/scope/scope.md`，采用 Tracer Bullet 构建方式。
2. 将项目拆分为基础层、最小端到端骨架、基线比较、跟踪与风险事件、证据链、Web、Agent 和比赛交付阶段。
3. 将模型训练、姿态微调、受限数据发布、云端多租户、手机端、数字孪生和多 Agent 列为延期内容。

证据：每个主动功能都定义了意图、出口条件和下一步命令；计划与 `agent.md`、架构快照和全局评估一致。

验证：已按 `scope` 技能的绿色项目、Tracer Bullet、基础设施优先和 Full 工作流规则检查范围结构。

影响：下一步固定为 `/architect stack and architecture`，在架构决定前不开始业务代码。

## 2026 年 8 月 29 日，完成技术栈与架构规格

范围：基础架构决策。

改动或发现：

1. 创建 `docs/specs/0001-stack-and-architecture.md`，确定模块化单体、Python 与 TypeScript、FastAPI、React、Vite、SQLite、独立 Worker、本地文件和 Docker Compose。
2. 固定 API 不执行 GPU 推理、任务状态持久化、结果版本化、Agent 只读证据和本地核心分析不依赖云端密钥等架构不变量。
3. 在范围文件中加入规格指针、工程骨架任务和验证任务。
4. 记录官方文档链接和第三方模型资料，未确认的社区技能不自动安装。

验证：已用 `git diff --check` 前置检查文件格式，并逐项核验规格中的官方链接可访问性。工程代码和运行验证尚未开始。

影响：下一步进入 `/develop stack and architecture`，建立真实目录、启动入口和依赖版本。规格状态保持 `Proposed`，待实现和验证后再接受。

## 2026 年 8 月 29 日，完成技术栈工程骨架

范围：基础架构脚手架。

改动：

1. 创建 Python 后端包，包含 FastAPI 应用、SQLite 任务表、任务状态接口和独立 Worker 入口。
2. 使用 Vite 创建 React 与 TypeScript 前端，并替换为中文工安智评工作台页面。
3. 添加 `pyproject.toml`、`.env.example`、后端 Dockerfile 和 Docker Compose 配置。
4. 添加后端健康检查和任务创建读取测试。

验证：前端 `npm run build` 和 `npm run lint` 通过，后端 `pytest` 通过两项测试，真实 Uvicorn 进程的健康接口和任务读写烟雾测试通过。测试环境出现一条 Starlette 关于 `httpx2` 的弃用提醒，当前不影响运行。

状态：架构规格推进为 `In Progress`，范围功能一保持 `in-progress`。下一步执行 `/check verify stack and architecture`，再进入数据契约规格。

## 2026 年 8 月 29 日，完成架构运行核验

范围：`/check verify stack and architecture`。

已观察证据：

1. 使用 `.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000` 启动 API，`GET /health` 返回 200 和版本 `0.1.0`。
2. `POST /api/tasks` 返回 201 和排队任务，随后 `GET /api/tasks/{id}` 返回相同任务。不存在的任务返回 404，空名称返回 422。
3. SQLite 实际存在 `analysis_tasks` 表及任务状态字段。独立 `python -m app.worker` 进程将排队任务更新为 `running`。
4. 使用 `npm run dev -- --host 127.0.0.1 --port 5173` 启动前端，页面返回 200，HTML 使用中文语言和标题。

结论：R-1、R-2 和 R-7 的脚手架行为已观察到。R-3、R-4、R-6 和 R-8 需要数据契约、视觉分析和 Agent 功能后才能核验，R-5 还需要浏览器人工检查，因此本次规格整体为 `BLOCKED`，范围中的 Verify 复选框保持未勾选。测试客户端仍有一条 Starlette 关于 `httpx2` 的弃用提醒。

下一步：先运行 `/architect data contract and persistence`，再实现文件存储、结果版本和证据结构。

## 2026 年 8 月 29 日，完成数据契约与持久化规格

范围：数据模型和持久化决策。

改动或发现：

1. 创建 `docs/specs/0002-data-contract-and-persistence.md`，确定九类核心实体、任务和运行状态机、版本化结果封装及组件来源记录。
2. 确定关系型核心加受控 JSON 的存储方式，视频、结果视频、报告和证据帧只保存文件引用，不把二进制写入数据库。
3. 固定上传、任务、运行、人员、风险事件和证据读取接口，所有列表接口使用游标分页，错误使用统一结构。
4. 为迁移、路径安全、原子文件写入、失败恢复和结果不可变性定义验收标准及测试场景。

验证：已检查规格章节、数据关系、值来源和每个验收标准对应的构建任务。尚未应用新迁移或实现数据层代码，规格状态保持 `Proposed`。

下一步：执行 `/develop data contract and persistence`，先建立 Alembic 迁移并确认空 SQLite 数据库的实际 schema。

## 2026 年 8 月 30 日，完成数据契约与持久化实现

范围：数据契约、SQLite 持久化、文件边界和读取接口。

改动：

1. 建立视频、任务、运行、组件、人员、逐帧观察、风险事件、证据帧和结果文件模型及 Alembic 初始迁移。
2. 增加 Pydantic 姿态、角度、REBA 和错误契约。
3. 增加本地视频上传、SHA256、大小和类型校验、原子写入、相对路径安全检查和 FFprobe 元数据读取。
4. 增加任务运行租约、运行重试、结果 JSON 原子写入、成功运行结果文件约束和分页读取接口。
5. 增加数据层专项测试，覆盖迁移表、结果完成条件、状态转换、重试和路径穿越。

验证：在临时 SQLite 数据库执行迁移，确认九类业务表和 Alembic 版本表存在；后端测试六项全部通过；上传和创建任务接口烟雾测试通过；提交 `4ad1d5d` 已推送到远程 `main`。

遗留：完整的模型推理结果写入流程、Worker 失败恢复和前端结果工作台仍属于后续端到端切片，数据契约功能还需独立 `/check verify` 和 `/test` 完成最终验收。

补充复核：规格复查后明确加入任务租约、取消请求、运行 `attempt`、视频元数据读取接口、JSON 坐标和 REBA 分数形状，以及旧脚手架数据库的处理策略，避免开发阶段出现未记录的承重决定。

## 2026 年 8 月 30 日，完成数据契约最终验收

范围：`/develop data contract and persistence` 收尾。

改动：

1. 正式任务接口强制 `video_asset_id`，同一视频的排队或运行任务返回统一 `video_busy` 错误；保留旧 `/api/tasks` 的 `source_name` 兼容入口。
2. 增加排队任务取消和运行中取消请求，Worker 领取任务时使用条件更新避免重复领取；失败重试重新排队，由 Worker 创建新的运行 attempt。
3. 修复统一错误响应的 HTTP 状态码传递、游标分页查询和结果 JSON 的 `fsync` 原子落盘。
4. 旧脚手架数据库不再被静默删除；未初始化或旧 schema 会提示先执行 Alembic。

验证：

1. `.venv/bin/pytest -q`：6 passed。
2. `.venv/bin/python -m compileall -q backend/app backend/alembic` 和 `git diff --check` 通过。
3. 在全新临时 SQLite 数据库执行 `ERGOAGENT_DATA_ROOT=<tmp> .venv/bin/alembic upgrade head`，确认九张业务表、外键、`uq_run_attempt` 唯一约束及风险事件索引均存在。

状态：数据契约与持久化实现完成；后续仍需独立 `/check verify data contract and persistence` 与 `/test data contract and persistence` 做流程级复核。

## 2026 年 8 月 30 日，完成 MVP 视频分析闭环

范围：最小端到端骨架和 Web 分析流程。

改动：

1. 接入本地 MediaPipe Pose 0.10.21、逐帧角度计算、reba-lite-0.1、连续高风险事件、证据帧和标注视频。
2. 前端接入真实视频上传、任务轮询、峰值 REBA、检测摘要、风险事件、证据帧和标注视频查看。
3. Worker 增加失败状态回写、取消请求收尾和缺失视频处理；结果产物提供安全读取接口。

验证：

1. 使用 4293956-uhd_3840_2160_25fps.mp4 完成真实运行：284 帧、252 帧检测成功、峰值 REBA 7、0 个高风险事件。
2. 空白视频验证为 analysis_failed / no_pose_detected，不产生伪造结果。
3. 后端回归测试、前端 lint/build、Python 编译和 git diff --check 通过。

状态：MVP 可运行；正式 REBA 标准映射、REBAPose 基线比较、多人员跟踪、Agent 和比赛材料仍未完成。

## 2026 年 8 月 30 日，完成后续 1～4 的可交付切片

范围：基线核验、跟踪接线、证据报告和结构化证据助手。

改动：

1. 新增 `CentroidTracker` 并接入分析器；逐帧观察、风险事件和结果 JSON 保存 `worker_id`/`track_id`。针对高分辨率视频按尺寸缩放匹配距离，并支持单轨迹漏检恢复。
2. 成功运行生成 HTML 与 JSON 双报告 artifact；增加 hash/大小/MIME 记录和安全内容读取接口。
3. 新增确定性证据助手：根据问题选择摘要、风险事件、证据帧和关节角度工具；回答引用具体运行、Worker、事件和证据帧。
4. 建立 REBAPose/AutoPostureCV baseline manifest；GitHub API 仅核验到仓库元数据，因浅克隆超时未宣称已完成同视频比较。

验证：

1. `.venv/bin/pytest -q`：10 passed。
2. `.venv/bin/python -m compileall -q backend/app backend/alembic` 和 `git diff --check` 通过。
3. `frontend`: `npm run lint`、`npm run build` 通过；Vite `http://127.0.0.1:5173/` 返回 200。
4. 真实 4K 视频回归：284 帧、252 帧检测、1 个稳定 Worker、峰值 REBA 7、0 个高风险事件；artifact 包含 `result_json`、`annotated_video`、`report`、`report_json`。

边界（当时记录）：当时仍是单人 MediaPipe 二维姿态和 `reba-lite-0.1` 辅助评估；后续记录已更新为标准表格代理评分和 HOG 多人实验模式，外部基线仍未形成可比指标。

## 2026 年 8 月 30 日，继续执行 1～4：基线清单、标准 REBA 和多人实验模式

范围：将后续 1～4 中可在本机验证的部分落到可审计实现，并保留外部运行时阻塞。

改动：

1. 新增 `docs/research/baseline-manifest.json` 和 `backend/app/baselines.py`，固定 REBAPose/AutoPostureCV 提交、许可证、入口、所需权重和阻塞原因；基线接口直接返回 manifest，不生成不可比指标。
2. 新增 `backend/app/reba.py`，使用 REBA 表 A/B/C 计算分项、Score A/B/C 和最终分数，视频不可观测的负荷、耦合、扭转和活动频率显式使用中性代理值，规则版本为 `reba-standard-proxy-0.2`。
3. 新增 `backend/app/detector.py`，支持 `ERGOAGENT_PERSON_DETECTOR=hog` 的 OpenCV HOG 多人候选框、置信度过滤和 IoU 抑制；每个候选框分别送入 MediaPipe，并保留 Worker ID 和检测器置信度。
4. 更新报告、README、范围和问题记录，明确 HOG 是实验能力，当前 4K 视频的多人候选仍有 ID 碎片化，不能替代专用多人姿态模型。

验证：

1. `.venv/bin/pytest -q`：13 passed；Python 编译和 `git diff --check` 通过。
2. 默认 MediaPipe 真实 4K 回归：284 帧、252 检测帧、1 个 Worker、峰值 REBA 9，四种结果 artifact 均生成。
3. HOG 实验真实 4K 回归成功完成，产生多个候选 Worker；结果显示 22 个 Worker、284 个检测帧（357 条人员观察）、平均置信度 0.745，已记录为质量阻塞而非完成声明。
4. 浏览器首屏、移动端 390×844 视口和视频选择交互通过 DOM/截图检查；首屏文案已切换到新规则版本。

状态：MVP 主线可运行；正式外部基线比较、专用多人 detector、视频负荷/耦合输入和浏览器完整上传到报告闭环仍待后续验证。
