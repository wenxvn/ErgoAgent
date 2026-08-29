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

当前前端按钮只演示任务状态变化，真实姿态和 REBA 分析将在后续垂直切片中接入。
