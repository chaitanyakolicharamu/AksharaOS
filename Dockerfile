FROM python:3.11-slim

WORKDIR /app

COPY requirements-docker.txt requirements-core.txt ./

RUN pip install --no-cache-dir -r requirements-docker.txt

COPY . .

RUN python -m knowledge.unified_build

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
