# 问题和风险记录

状态：开放问题按优先级排列，关闭时保留证据。

## I 001，官方赛事详情接口需要授权

优先级：高，状态：开放。

现象：2026 年 8 月 29 日访问官网详情页可以得到前端页面，但直接调用 `api.g-ican.com/v1/api/competitionInfo/detail` 返回缺少 `Authorization`。

影响：无法仅靠未授权接口确认详情正文和历届作品清单。

处理：把用户提供的 2026 年 7 月 22 日 AI 应用创新挑战赛通知作为当前一手材料，同时在报名和提交前由参赛者登录官网或向组委会确认赛程、材料格式、双赛报名限制和赛区规则。

## I 002，第三方仓库和数据许可需要逐项核验

优先级：高，状态：开放。

现象：GitHub API 显示 `REBAPose` 为 MIT，`MotionBERT` 为 Apache 2.0，`AutoPostureCV_Public` 为 MIT；`CP3D` 仓库元数据没有声明许可证，README 提供短链接和作者邮箱。

影响：CP3D 数据和代码不能在许可证确认前作为公开发布或参赛交付的默认依赖。

处理：建立外部资料清单，保存访问日期、提交号、许可证文本、数据使用条件和权重来源。必要时邮件向作者确认授权，未确认前只做本地研究。

## I 003，核心视觉业务代码已实现但仍有模型边界

优先级：高，状态：开放。

现象：当前仓库已实现 MediaPipe 二维姿态、角度、标准表格代理 REBA、风险事件、证据和结构化助手；正式三维姿态、负荷/耦合输入和专家复核仍未接入。

影响：比赛可行性目前仍是规划判断，架构运行核验只能覆盖任务和进程边界。

处理：保留可验证的二维离线主线，所有不可观测项在结果中显式记录中性代理值，并把 REBAPose/三维模型作为独立基线复现工作。

## I 004，测试客户端出现 httpx2 弃用提醒

优先级：低，状态：记录。

现象：当前 FastAPI 测试使用的 Starlette TestClient 提示未来将推荐 `httpx2`。

影响：现阶段测试可以正常运行，后续依赖升级时可能需要调整测试依赖或导入方式。

处理：暂不改变生产依赖，保留当前两项测试。执行 `/audit tooling` 或升级 FastAPI 测试栈时重新核验。

## I 005，视觉依赖的 Python 版本边界

优先级：中，状态：记录。

现象：MediaPipe 0.10.21 的 `mp.solutions.pose` API 在 Python 3.12 可用，但当前 Python 3.13/3.14 环境没有兼容轮子。

处理：MVP 固定使用 `.venv-vision312` 运行 Worker；后续若迁移 MediaPipe Tasks API，需要单独核验模型文件来源、版本和许可证。

## I 006，外部基线未完成本地复现

优先级：高，状态：开放。

现象：已固定 REBAPose `185391a...` 和 AutoPostureCV `82a69f...`。REBAPose 入口和所需权重/依赖已从仓库内容核验；AutoPostureCV 该提交只有 README/LICENSE，没有可运行源码。

影响：`/api/analysis-runs/{run_id}/baseline` 只能报告 MediaPipe 已执行事实，候选模型保持 `not_integrated`，不能提供同视频比较指标。

处理：信息写入 `docs/research/baseline-manifest.json`，接口返回 `blocked_external_runtime` / `blocked_no_source_at_commit`，不生成不可比指标。后续获取完整运行时后再固定依赖锁、权重 SHA256 并运行同视频 benchmark。

## I 007，浏览器运行时验证

优先级：中，状态：已关闭（2026-08-30）。

现象：原先记录的插件路径已变更；从当前 bundled browser runtime 建立连接后可执行 DOM 和截图检查，项目仍未安装 Playwright。

处理：已完成 Vite HTTP 200、lint、production build、首屏 DOM、390×844 移动视口截图和本地视频选择交互验证；完整上传到报告闭环仍由后端 API 回归覆盖。
