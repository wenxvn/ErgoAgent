from __future__ import annotations
import hashlib
import os
import tempfile
import json
import subprocess
from pathlib import Path, PurePosixPath
from uuid import uuid4
from fastapi import UploadFile, HTTPException
from .config import DATA_ROOT

ALLOWED_MIME = {'video/mp4','video/quicktime','video/webm','video/x-msvideo','video/mpeg'}
MAX_UPLOAD_BYTES = int(os.getenv('ERGOAGENT_MAX_UPLOAD_BYTES', 2 * 1024 * 1024 * 1024))

def resolve_safe(relative: str, area: str | None = None) -> Path:
    rel = PurePosixPath(relative)
    if rel.is_absolute() or '..' in rel.parts:
        raise ValueError('path must stay within data root')
    root = (Path(DATA_ROOT) / area) if area else Path(DATA_ROOT)
    path = (root / Path(*rel.parts)).resolve()
    if path != root.resolve() and root.resolve() not in path.parents:
        raise ValueError('path must stay within data root')
    return path

async def save_upload(upload: UploadFile) -> tuple[str, str, int]:
    if upload.content_type not in ALLOWED_MIME:
        raise HTTPException(400, detail={'code':'unsupported_type','message':'unsupported video type','details':{}})
    area = Path(DATA_ROOT) / 'uploads'; area.mkdir(parents=True, exist_ok=True)
    name = f'{uuid4()}{Path(upload.filename or "video").suffix.lower()}'
    target = area / name
    digest = hashlib.sha256(); size = 0
    fd, temp_name = tempfile.mkstemp(prefix='.upload-', dir=area)
    try:
        with os.fdopen(fd, 'wb') as out:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, detail={'code':'upload_too_large','message':'upload exceeds size limit','details':{}})
                digest.update(chunk); out.write(chunk)
            out.flush(); os.fsync(out.fileno())
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name): os.unlink(temp_name)
    return str(PurePosixPath('uploads') / name), digest.hexdigest(), size

def remove_relative(relative_path: str) -> None:
    path = resolve_safe(relative_path)
    path.unlink(missing_ok=True)

def media_metadata(relative_path: str) -> dict:
    path = resolve_safe(relative_path)
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,r_frame_rate:format=duration', '-of', 'json', str(path)],
            check=True, capture_output=True, text=True, timeout=30,
        )
        data = json.loads(result.stdout)
        stream = (data.get('streams') or [{}])[0]
        duration = (data.get('format') or {}).get('duration')
        rate = stream.get('r_frame_rate', '')
        fps = None
        if '/' in rate:
            numerator, denominator = rate.split('/', 1)
            if float(denominator): fps = float(numerator) / float(denominator)
        return {'duration_ms': round(float(duration) * 1000) if duration else None, 'width': stream.get('width'), 'height': stream.get('height'), 'fps': fps}
    except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError):
        return {}
