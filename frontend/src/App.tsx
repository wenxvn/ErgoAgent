import { useState } from 'react'
import './App.css'

type TaskState = '待分析' | '分析中' | '待接入'

function App() {
  const [taskState, setTaskState] = useState<TaskState>('待分析')

  const startDemo = () => {
    setTaskState('分析中')
    window.setTimeout(() => setTaskState('待接入'), 1200)
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true">工</span>
          <div>
            <p className="eyebrow">ERGOAGENT / 工安智评</p>
            <h1>职业工效风险工作台</h1>
          </div>
        </div>
        <span className="system-status"><span aria-hidden="true" />本地分析环境</span>
      </header>

      <section className="intro" aria-labelledby="intro-title">
        <div>
          <p className="section-kicker">分析入口</p>
          <h2 id="intro-title">把作业视频变成可追溯的风险证据</h2>
          <p className="intro-copy">当前骨架已准备好任务状态、结果版本和证据文件边界，下一步接入姿态与 REBA 分析。</p>
        </div>
        <button className="primary-action" type="button" onClick={startDemo}>
          {taskState === '分析中' ? '正在创建任务…' : '运行骨架演示'}
        </button>
      </section>

      <section className="dashboard-grid" aria-label="系统概览">
        <article className="panel panel-wide">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">最近任务</p>
              <h3>sample-worksite.mp4</h3>
            </div>
            <span className={`status-pill status-${taskState === '待分析' ? 'idle' : taskState === '分析中' ? 'running' : 'queued'}`}>{taskState}</span>
          </div>
          <div className="timeline" aria-label="分析阶段">
            <div className="timeline-step active"><span>01</span><strong>任务登记</strong><small>已写入 SQLite</small></div>
            <div className={`timeline-step ${taskState !== '待分析' ? 'active' : ''}`}><span>02</span><strong>视觉分析</strong><small>等待 REBAPose</small></div>
            <div className="timeline-step"><span>03</span><strong>风险证据</strong><small>等待结果契约</small></div>
          </div>
        </article>

        <article className="panel metric-panel">
          <p className="section-kicker">数据边界</p>
          <div className="metric-value">本地优先</div>
          <p className="metric-note">视频、结果和证据帧保存于 data/</p>
        </article>

        <article className="panel metric-panel accent-panel">
          <p className="section-kicker">服务状态</p>
          <div className="metric-value">API 在线</div>
          <p className="metric-note">FastAPI · SQLite · Worker</p>
        </article>
      </section>

      <footer className="footer-note">架构版本 0.1.0 · 分析结论仅用于辅助评估和风险提示</footer>
    </main>
  )
}

export default App
