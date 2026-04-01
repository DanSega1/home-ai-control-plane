FROM python:3.14-slim

WORKDIR /app

# Build context is the project root (see infra/docker-compose.yml)
COPY constraints.txt .
COPY services/skill-runner/requirements.txt .
RUN pip install --no-cache-dir -c constraints.txt -r requirements.txt

COPY contracts /app/contracts

COPY services/skill-runner/app/ /app/app/
COPY services/skill-runner/main.py /app/

# skills/ is mounted at runtime via docker-compose volume (../skills:/app/skills:ro)
# so the registry.yaml and skill.ref.yaml files are always up-to-date without rebuilds.

EXPOSE 8002

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
