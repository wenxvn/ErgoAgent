# ErgoAgent 工安智评

ErgoAgent 是面向工业作业场景的职业工效风险辅助评估软件。当前仓库处于工程骨架阶段，已具备前端、FastAPI 后端、SQLite 任务状态和独立 Worker 的启动边界。

## 本地启动

先安装依赖：

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
cd frontend && npm install
```

启动后端：

```bash
.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

启动前端：

```bash
cd frontend && npm run dev
```

前端地址是 `http://localhost:5173`，后端健康检查是 `http://127.0.0.1:8000/health`。

## 目录

- `backend/app/`：FastAPI 应用、数据库和 Worker
- `backend/tests/`：后端测试
- `frontend/`：React 与 Vite 前端
- `data/`：本地视频、结果和证据文件目录
- `docs/`：架构、范围、研究和长期记录
- `skills/`：项目工作流技能

## MVP 分析流程

MVP 已包含真实的视频上传、任务排队、独立 Worker 分析、MediaPipe Pose 二维姿态、角度计算、REBA 标准表格代理评分、风险事件、证据帧和结果 JSON。前端会轮询任务状态，并在成功后展示风险事件、证据帧、报告和证据助手。

启动顺序：

```bash
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
.venv-vision312/bin/python -m app.worker
cd frontend && npm run dev -- --host 127.0.0.1 --port 5173
```

默认使用已验证的单人 MediaPipe Pose。需要测试多人候选框时，在启动 Worker 前设置 `ERGOAGENT_PERSON_DETECTOR=hog`；它使用 OpenCV 内置 HOG 行人检测器，将每个候选框分别送入姿态模型，并把检测器置信度写入逐帧边界框。HOG 不是施工场景专用模型，遮挡、交叉和漏检必须通过证据帧人工复核。

视觉 Worker 使用 Python 3.12，因为当前 MediaPipe 旧版 `mp.solutions.pose` API 没有 Python 3.13/3.14 的兼容轮子。首次安装视觉环境：

```bash
uv venv --python 3.12 .venv-vision312
uv pip install --python .venv-vision312/bin/python 'mediapipe==0.10.21' opencv-python numpy
uv pip install --python .venv-vision312/bin/python -e .
```

当前评分使用 `reba-standard-proxy-0.2`：采用 REBA 表格，视频未提供的负荷、耦合、扭转和活动频率显式采用中性值，不替代人工填写的正式 REBA 表。结论仅用于辅助评估和风险提示。模型不可用、视频无法读取或未检测到姿态时，任务会失败，不会生成伪造结果。视频、结果和证据文件只保存到 `data/` 下，数据库只保存相对路径和校验信息。

生成一个用于接口冒烟测试的视频（需要 FFmpeg）：

```bash
ffmpeg -f lavfi -i color=c=black:s=320x240:d=2 -y sample.mp4
```
