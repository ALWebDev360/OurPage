FROM python:3.13-slim

WORKDIR /app

# Runtime libs for lxml (no -dev / gcc needed — using pre-built wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 \
    libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps (binary wheels only — no compilation)
COPY requirements.txt .
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

# Copy app code (kept small via .dockerignore / .flyignore)
COPY . .

EXPOSE 8080

CMD ["gunicorn", "audit_server:app", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "120"]
