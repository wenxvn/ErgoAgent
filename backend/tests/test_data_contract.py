from pathlib import Path
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from app.db import Base, AnalysisRun, AnalysisTask, VideoAsset, new_task
from app.services import complete_run, create_retry_run, transition_task, write_result_json
from app.storage import resolve_safe

def test_schema_has_contract_tables(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    assert set(inspect(engine).get_table_names()) >= {
        'video_assets', 'analysis_tasks', 'analysis_runs', 'run_components',
        'workers', 'frame_observations', 'risk_events', 'evidence_frames', 'result_artifacts'
    }

def test_run_completion_requires_result(tmp_path, monkeypatch):
    monkeypatch.setattr('app.services.DATA_ROOT', tmp_path)
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    video = VideoAsset(original_name='x.mp4', storage_path='uploads/x.mp4', sha256='a' * 64, size_bytes=1, mime_type='video/mp4')
    task = new_task('x.mp4')
    db.add(video); db.flush(); task.video_asset_id = video.id
    db.add(task); db.commit()
    run = AnalysisRun(task_id=task.id, attempt=1, status='running', input_video_id=video.id)
    db.add(run); transition_task(task, 'running'); db.commit()
    try:
        complete_run(db, run, 'succeeded')
    except ValueError:
        pass
    else:
        assert False, 'a successful run without result_json must fail'
    write_result_json(db, run, {'schema_version': '1.0', 'frames': []})
    complete_run(db, run, 'succeeded'); db.commit()
    assert run.status == 'succeeded' and task.status == 'succeeded'

def test_transitions_and_retry(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    task = new_task('x.mp4'); db.add(task); db.commit()
    transition_task(task, 'running'); transition_task(task, 'failed'); db.commit()
    retry = create_retry_run(db, task); db.commit()
    assert task.status == 'running' and retry.attempt == 1
    assert retry.status == 'running'

def test_path_traversal_rejected():
    try:
        resolve_safe('../secret.txt')
    except ValueError:
        pass
    else:
        assert False, 'path traversal must be rejected'
