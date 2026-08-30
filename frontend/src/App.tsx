import { useEffect, useMemo, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import './App.css'

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
type Task = { id: string; status: string; source_name: string; run_id?: string; error_message?: string }
type Run = { id: string; status: string; model_summary: { frames?: number; detected_frames?: number; fps?: number; mean_confidence?: number; peak_reba?: number; detector?: string }; ruleset_version: string; artifacts?: { kind: string }[]; error_message?: string }
type Event = { id: string; start_ms: number; end_ms: number; peak_score: number; mean_score: number; body_region: string; confidence: number }
type EventDetail = Event & { evidence_frames: { id: string; frame_index: number; reason: string }[] }

function formatTime(ms: number) { return `${(ms / 1000).toFixed(1)}s` }

export default function App() {
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [task, setTask] = useState<Task | null>(null)
  const [run, setRun] = useState<Run | null>(null)
  const [events, setEvents] = useState<Event[]>([])
  const [selected, setSelected] = useState<EventDetail | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [question, setQuestion] = useState('为什么这段视频没有高风险事件？')
  const [assistantAnswer, setAssistantAnswer] = useState<{ answer: string; tool_calls: { tool: string }[] } | null>(null)

  useEffect(() => {
    if (!task || !['queued', 'running'].includes(task.status)) return
    const timer = window.setInterval(async () => {
      const response = await fetch(`${API}/api/analysis-tasks/${task.id}`)
      if (!response.ok) return
      const next = await response.json() as Task
      setTask(next)
      if (next.status === 'failed') setError(next.error_message || '分析失败')
      if (next.status === 'succeeded' && next.run_id) {
        const nextRun = await (await fetch(`${API}/api/analysis-runs/${next.run_id}`)).json() as Run
        setRun(nextRun)
        const eventResponse = await fetch(`${API}/api/analysis-runs/${next.run_id}/risk-events`)
        setEvents((await eventResponse.json()).items || [])
      }
    }, 1500)
    return () => window.clearInterval(timer)
  }, [task])

  const statusLabel = useMemo(() => ({ queued: '排队中', running: '分析中', succeeded: '已完成', failed: '失败', cancelled: '已取消' }[task?.status || ''] || '待上传'), [task])
  async function startAnalysis() {
    if (!file) return
    setBusy(true); setError(''); setRun(null); setEvents([]); setSelected(null)
    try {
      const body = new FormData(); body.append('file', file)
      const upload = await fetch(`${API}/api/videos`, { method: 'POST', body }); const uploaded = await upload.json()
      if (!upload.ok) throw new Error(uploaded.error?.message || '视频上传失败')
      const create = await fetch(`${API}/api/analysis-tasks`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ video_asset_id: uploaded.video_asset_id }) }); const created = await create.json()
      if (!create.ok) throw new Error(created.error?.message || '任务创建失败')
      setTask(created)
    } catch (caught) { setError(caught instanceof Error ? caught.message : '请求失败') } finally { setBusy(false) }
  }
  async function selectEvent(event: Event) { const response = await fetch(`${API}/api/risk-events/${event.id}`); if (response.ok) setSelected(await response.json()) }
  async function askAssistant() {
    if (!run || !question.trim()) return
    const response = await fetch(`${API}/api/analysis-runs/${run.id}/assistant`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }) })
    if (response.ok) setAssistantAnswer(await response.json())
  }
  function chooseFile(event: ChangeEvent<HTMLInputElement>) { setFile(event.target.files?.[0] || null); setError(''); setTask(null); setRun(null); setEvents([]); setSelected(null) }

  return <main className="shell">
    <header className="topbar"><div className="brand-lockup"><span className="brand-mark" aria-hidden="true">工</span><div><p className="eyebrow">ERGOAGENT / 工安智评</p><h1>职业工效风险工作台</h1></div></div><span className="system-status"><span aria-hidden="true" />本地分析环境</span></header>
    <section className="intro"><div><p className="section-kicker">分析入口</p><h2>把作业视频变成可追溯的风险证据</h2><p className="intro-copy">上传一段作业视频，Worker 将在本地完成姿态、角度和 REBA 辅助评估。</p></div><div className="upload-actions"><input ref={inputRef} type="file" accept="video/*" onChange={chooseFile} hidden /><button className="secondary-action" type="button" onClick={() => inputRef.current?.click()}>选择视频</button><button className="primary-action" type="button" disabled={!file || busy || !!task && ['queued', 'running'].includes(task.status)} onClick={startAnalysis}>{busy ? '上传中…' : '开始分析'}</button></div></section>
    {file && <div className="file-strip"><strong>{file.name}</strong><span>{(file.size / 1024 / 1024).toFixed(1)} MB</span>{task && <span className={`status-pill status-${task.status}`}>{statusLabel}</span>}</div>}
    {error && <div className="notice error-notice">{error}</div>}
    <section className="dashboard-grid"><article className="panel panel-wide"><div className="panel-heading"><div><p className="section-kicker">任务状态</p><h3>{task?.source_name || '尚未选择视频'}</h3></div>{task && <span className={`status-pill status-${task.status}`}>{statusLabel}</span>}</div><div className="timeline"><div className={`timeline-step ${file ? 'active' : ''}`}><span>01</span><strong>视频登记</strong><small>{file ? '已选择文件' : '等待上传'}</small></div><div className={`timeline-step ${task ? 'active' : ''}`}><span>02</span><strong>视觉分析</strong><small>{task ? statusLabel : '等待任务'}</small></div><div className={`timeline-step ${run?.status === 'succeeded' ? 'active' : ''}`}><span>03</span><strong>风险证据</strong><small>{run ? `${events.length} 个事件` : '等待结果'}</small></div></div></article><article className="panel metric-panel"><p className="section-kicker">峰值 REBA</p><div className="metric-value">{run?.model_summary.peak_reba ?? '—'}</div><p className="metric-note">规则版本 {run?.ruleset_version || 'reba-standard-proxy-0.2'}</p></article><article className="panel metric-panel accent-panel"><p className="section-kicker">检测摘要</p><div className="metric-value">{run ? `${run.model_summary.detected_frames || 0} / ${run.model_summary.frames || 0}` : '—'}</div><p className="metric-note">检测帧 / 总帧数</p></article></section>
    {run?.status === 'succeeded' && <section className="results"><div className="section-heading"><div><p className="section-kicker">风险事件</p><h3>按时间定位需要复核的片段</h3></div><div className="result-links"><span className="muted">{run.model_summary.fps?.toFixed(1) || '—'} FPS · {run.ruleset_version}</span>{run.artifacts?.some(artifact => artifact.kind === 'result_json') && <a href={`${API}/api/analysis-runs/${run.id}/artifacts/result_json/content`} target="_blank" rel="noreferrer">下载结果 JSON</a>}{run.artifacts?.some(artifact => artifact.kind === 'report') && <a href={`${API}/api/analysis-runs/${run.id}/artifacts/report/content`} target="_blank" rel="noreferrer">查看证据报告</a>}{run.artifacts?.some(artifact => artifact.kind === 'report_json') && <a href={`${API}/api/analysis-runs/${run.id}/artifacts/report_json/content`} target="_blank" rel="noreferrer">下载报告 JSON</a>}{run.artifacts?.some(artifact => artifact.kind === 'annotated_video') && <a href={`${API}/api/analysis-runs/${run.id}/artifacts/annotated_video/content`} target="_blank" rel="noreferrer">查看标注视频</a>}</div></div>{(run.model_summary.mean_confidence ?? 1) < 0.6 && <div className="notice">平均姿态置信度较低（{((run.model_summary.mean_confidence || 0) * 100).toFixed(0)}%），请复核证据帧后再使用。</div>}{events.length === 0 ? <div className="empty">未发现达到高风险阈值的连续片段。</div> : <div className="event-list">{events.map(event => <button className={`event-row ${selected?.id === event.id ? 'selected' : ''}`} key={event.id} onClick={() => selectEvent(event)}><span className="event-score">{event.peak_score}</span><span><strong>{formatTime(event.start_ms)} — {formatTime(event.end_ms)}</strong><small>{event.body_region} · 平均 {event.mean_score} · 置信度 {(event.confidence * 100).toFixed(0)}%</small></span><span className="arrow" aria-hidden="true">›</span></button>)}</div>}</section>}
    {selected && <section className="detail"><div><p className="section-kicker">事件证据</p><h3>帧 {selected.evidence_frames.map(frame => frame.frame_index).join(', ') || '—'}</h3><p className="metric-note">{selected.evidence_frames.length} 张证据帧 · {selected.evidence_frames[0]?.reason}</p></div><div className="evidence-grid">{selected.evidence_frames.map(frame => <img key={frame.id} src={`${API}/api/evidence-frames/${frame.id}/content`} alt={`证据帧 ${frame.frame_index}`} />)}</div></section>}
    {run?.status === 'succeeded' && <section className="assistant"><div><p className="section-kicker">证据助手</p><h3>基于本次运行事实追问</h3><p className="metric-note">回答只读取已保存的姿态、角度、REBA 和事件数据。</p></div><div className="assistant-form"><input value={question} onChange={event => setQuestion(event.target.value)} aria-label="向证据助手提问" /><button className="secondary-action" type="button" onClick={askAssistant}>查询</button></div>{assistantAnswer && <div className="assistant-answer"><p>{assistantAnswer.answer}</p><small>工具调用：{assistantAnswer.tool_calls.map(call => call.tool).join(' · ')}</small></div>}</section>}
    <footer className="footer-note">架构版本 0.1.0 · 分析结论仅用于辅助评估和风险提示</footer>
  </main>
}
