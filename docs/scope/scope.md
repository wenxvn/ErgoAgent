# Scope: ErgoAgent

ErgoAgent 是面向建筑、制造、仓储和物流作业的职业工效风险辅助评估软件。它从公开作业视频中提取人员姿态、连续风险事件和可追溯证据，并通过受约束的 Agent 生成解释和整改建议。

**Build approach:** 垂直切片（Tracer Bullet，先打通一条真实的输入、分析、存储、接口和界面链路，再逐段加厚）。
**Workflow:** 完整流程（Full，开发后执行真实验证、测试、独立复核和比赛文档整理；涉及长期维护、外部数据许可和比赛交付）。

## 规划假设

1. 第一阶段以单机离线分析和单用户演示为目标，不先承诺云端多租户。
2. 不自采数据，使用公开视频、公开数据和许可证明确的预训练权重。
3. 第一阶段不训练大型模型，先验证现成模型和可解释规则。
4. 结论使用“辅助评估”和“风险提示”，不宣称医疗诊断或职业病诊断。
5. 赛事规则、截止时间和作品要求以当届官网及组委会通知为准。

## 总览

| # | Feature | Phase | Status |
|---|---------|-------|--------|
| 1 | 技术栈与架构 | 基础 | in-progress |
| 2 | 编码规范与工具链 | 基础 | planned |
| 3 | 数据契约与持久化 | 基础 | planned |
| 4 | 设计系统与界面基础 | 基础 | planned |
| 5 | 最小端到端骨架，一段视频到一份结果 | 骨架 | planned |
| 6 | 基线可复现与对比 | 切片二 | planned |
| 7 | 多人员跟踪与风险事件 | 切片三 | planned |
| 8 | 证据链与报告 | 切片四 | planned |
| 9 | Web 分析流程 | 切片五 | planned |
| 10 | 姿态证据驱动的 ErgoAgent | 切片六 | planned |
| 11 | 比赛材料与演示 | 切片七 | planned |
| 12 | 模型适配与高级部署 | 延期 | planned |

## 基础阶段

### 1. 技术栈与架构 · in-progress · Medium

确定语言、服务边界、前后端形态、推理任务运行方式、文件和数据库边界，并建立可启动的工程骨架。
**Done when:** 架构决策有规格记录，项目可在本地启动，核心目录和运行入口已经固定。
- [x] 设计并记录架构决定：`/architect stack and architecture`，规格见 [`docs/specs/0001-stack-and-architecture.md`](../specs/0001-stack-and-architecture.md)
- [x] 依据规格建立工程骨架：`/develop stack and architecture`，代码位于 `backend/`、`frontend/`，启动配置位于 `docker-compose.yml`
- [ ] 验证本地启动、任务状态和关键边界：`/check verify stack and architecture`

### 2. 编码规范与工具链

从真实工程骨架中确定中文文档、代码格式、静态检查、测试入口、提交规范和敏感信息检查。
**Done when:** 根上下文和工具配置反映真实工程，检查命令在本地可执行。
- [ ] 采集约定和工具选择：`/audit`
- [ ] 安装和配置工具：`/develop tooling`
- [ ] 验证工具链：`/check verify tooling`

### 3. 数据契约与持久化 · planned · Full

为视频、人员、帧、姿态、角度、规则结果、风险事件、证据帧和分析任务定义稳定的数据契约。
**Done when:** 统一 JSON、持久化结构、版本字段、错误状态和迁移策略可以支持后续分析、前端和 Agent，不依赖重新解析历史结果。
- [x] 设计数据契约和存储决定：`/architect data contract and persistence`，规格见 [`docs/specs/0002-data-contract-and-persistence.md`](../specs/0002-data-contract-and-persistence.md)
- [ ] 实现模型、迁移、文件存储和读取接口：`/develop data contract and persistence`
- [ ] 验证迁移、状态机、分页和路径安全：`/check verify data contract and persistence`
- [ ] 固化数据契约和失败场景测试：`/test data contract and persistence`

### 4. 设计系统与界面基础 · needs a decision

定义分析工作台的布局、状态、风险色彩、时间轴、证据帧和可访问交互，保证比赛演示与日常使用一致。
**Done when:** 基础页面结构、状态组件、错误提示和键盘操作规则已经记录，可承载最小分析闭环。
- [ ] 设计界面基础：`/architect design system and UI foundation`

## 骨架阶段

### 5. 最小端到端骨架，一段视频到一份结果 · needs a decision · Full

打通一条真实链路：输入一段公开视频，完成人员检测、姿态推理、角度和单帧 REBA 计算，输出 JSON 与带标注视频。
**Done when:** 一个固定公开样例可以重复运行，输出包含模型和规则版本，失败输入有明确错误，核心结果不是手工填写。
- [ ] 设计最小端到端路径：`/architect walking skeleton`

## 切片二

### 6. 基线可复现与对比 · needs a decision

在同一组固定样例上比较 REBAPose 与 AutoPostureCV，记录准确性代理指标、角度稳定性、速度、遮挡、多人员和失败案例。
**Done when:** 每次比较可由固定命令复现，结果和环境写入实验记录，并明确哪些组件进入主线。
- [ ] 设计基线比较和实验记录方式：`/architect baseline comparison`

## 切片三

### 7. 多人员跟踪与风险事件 · needs a decision · Full

将逐帧结果关联为稳定的 Worker ID，并把连续高风险帧聚合为包含持续时间、峰值、平均分、重复次数和置信度的 RiskEvent。
**Done when:** 多人员视频中人员身份跨帧稳定，风险事件可定位起止时间，遮挡和跟踪不确定性被显式标记。
- [ ] 设计跟踪和风险事件规则：`/architect multi worker tracking and risk events`

## 切片四

### 8. 证据链与报告 · needs a decision · Full

把每个风险结论绑定到人员、时间、关节、角度、置信度、REBA 规则和证据帧，并输出可审查的结构化报告。
**Done when:** 用户可以从风险摘要跳转到证据帧，报告能列出来源、版本、限制和未确定项。
- [ ] 设计证据链和报告契约：`/architect evidence chain and report`

## 切片五

### 9. Web 分析流程 · needs a decision

提供上传、分析任务状态、结果视频、人员排行、风险时间轴、证据帧和报告导出的完整用户路径。
**Done when:** 用户可以从上传开始完成一次分析并查看结果，处理中、失败、空结果和低置信度状态都可理解。
- [ ] 设计 Web 分析流程：`/architect web analysis workflow`

## 切片六

### 10. 姿态证据驱动的 ErgoAgent · needs a decision · Full

让 Agent 通过明确工具查询人员摘要、风险事件、关节角度、REBA 细节、视频时间和专业规则，再生成带证据的解释和整改建议。
**Done when:** 用户提出“为什么风险高”或“查看证据”时，系统展示工具调用和证据来源；模型不可用时基础分析仍可运行。
- [ ] 设计 Agent 工具协议和失败边界：`/architect pose grounded ErgoAgent`

## 切片七

### 11. 比赛材料与演示 · needs a decision · Full

基于同一核心系统制作“工安智评”创新赛道版本和“ErgoAgent”AI 应用挑战赛版本，整理应用方案、演示视频、运行说明和原创证据链。
**Done when:** 两个版本的叙事、材料、链接、源码和许可证记录分别通过提交检查，演示视频完整展示请求、分析、工具协同、反馈和追问闭环。
- [ ] 设计双赛道材料和演示验收：`/architect competition packaging and demo`

## 延期内容

以下内容保留在规划中，但不阻塞当前比赛版本：

- **轻量时序模型训练**：仅在规则模型和基线比较证明必要时进入范围。
- **姿态模型微调**：仅在公开权重无法满足固定场景稳定性时评估。
- **CP3D 深度训练和受限数据发布**：许可证和算力确认前只做内部研究。
- **云端多租户、账号、权限和计费**：比赛单机或单用户演示完成后再决定。
- **手机端、数字孪生、AR 和多 Agent**：除非赛事规则或用户需求明确要求，否则不做。

## 下一步

当前第一个未完成事项是 `/architect data contract and persistence` 的实现。完成数据契约规格后，按顺序执行迁移、文件存储、结果接口和测试，再进入最小端到端路径。每个功能完成后必须同步 `agent.md` 所列的架构、变更、决策、问题、研究和比赛记录。

## 状态说明

`planned` 表示尚未设计和实现，`in-progress` 表示已经开始但未完成，`done` 表示按当前工作流完成验证和记录，`dropped` 表示保留历史但不再实施。每个功能的原子任务进入对应规格，不把代码任务清单复制到本文件。
