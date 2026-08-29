FROM python:3.12-slim

WORKDIR /workspace
COPY pyproject.toml ./
COPY backend ./backend
RUN pip install --no-cache-dir .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
