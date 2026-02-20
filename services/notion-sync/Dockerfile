FROM python:3.12-slim

WORKDIR /app

# Build context is the project root (see infra/docker-compose.yml)
COPY constraints.txt .
COPY services/notion-sync/requirements.txt .
RUN pip install --no-cache-dir -c constraints.txt -r requirements.txt

COPY contracts /app/contracts

COPY services/notion-sync/app/ /app/app/
COPY services/notion-sync/main.py /app/

EXPOSE 8003

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
