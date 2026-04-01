FROM python:3.14-slim

WORKDIR /app

# Install deps first for layer caching
# Build context is the project root (see infra/docker-compose.yml)
COPY constraints.txt .
COPY services/supervisor/requirements.txt .
RUN pip install --no-cache-dir -c constraints.txt -r requirements.txt

# Copy shared contracts
COPY contracts /app/contracts

# Copy service source
COPY services/supervisor/app/ /app/app/
COPY services/supervisor/main.py /app/

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
