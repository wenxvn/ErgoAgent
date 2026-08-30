# 0003. 最小视频分析闭环

**Status**: Ratified for MVP
**Date**: 2026-08-30
**Authorized by**: 工程师，在开发 MVP 时

## Decision

MVP 采用本地 MediaPipe Pose 0.10.21 作为二维姿态基线，使用 `reba-standard-proxy-0.2` 的 REBA 表 A/B/C 计算姿态风险。视频不可观测的负荷、耦合、扭转和活动频率显式采用中性代理值；该规则用于辅助评估，不代表完整职业工效诊断。

## Assumption built on

MVP 使用本地 MediaPipe Pose 作为可离线运行的二维姿态基线，使用明确记录的简化 REBA 规则计算躯干、膝和上肢风险。模型不可用时任务失败，不生成伪造结果。正式 REBA 标准映射、REBAPose 对比和多人员跟踪留在后续切片；在完成前，产品只输出辅助评估和风险提示。

## Code area

backend/app/analysis.py、backend/app/worker.py、backend/app/main.py、frontend/src/、README.md。

## Requirements

- 上传一段本地视频后创建分析任务。
- Worker 逐帧提取人员姿态，输出角度、REBA 分数、风险等级和置信度。
- 高风险连续帧聚合为风险事件，并保留证据帧。
- 前端显示上传、任务状态、人员摘要、风险事件和证据图。
- 模型运行环境缺失或输入无效时，任务明确失败，不输出确定性伪结果。

## Verification

2026-08-30 已用真实 H.264 视频验证：284 帧中检测到 252 帧，MediaPipe 0.10.21 正常运行，最高逐帧 REBA 为 7，未达到高风险事件阈值 8；空白视频会明确失败为 no_pose_detected。视觉 Worker 固定使用 Python 3.12 环境。
