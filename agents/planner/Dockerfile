FROM python:3.13-slim

WORKDIR /app

# Build context is the project root (see infra/docker-compose.yml)
COPY constraints.txt .
COPY agents/planner/requirements.txt .
RUN pip install --no-cache-dir -c constraints.txt -r requirements.txt

# Shared contracts
COPY contracts /app/contracts

COPY agents/planner/app/ /app/app/
COPY agents/planner/main.py /app/

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
