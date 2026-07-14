FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libsm6 libxext6 libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY rules.py agent.py config.yaml ./

# Default: dry-run on first start is safer — override in compose command
CMD ["python", "agent.py", "--config", "/app/config.yaml"]
