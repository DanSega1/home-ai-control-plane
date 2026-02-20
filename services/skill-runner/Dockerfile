FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ../../contracts /app/contracts

COPY app/ /app/app/
COPY main.py /app/

# skills/ is mounted at runtime via docker-compose volume (../skills:/app/skills:ro)
# so the registry.yaml and skill.ref.yaml files are always up-to-date without rebuilds.

EXPOSE 8002

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
