FROM python:3.11-slim

WORKDIR /app

# Copy package definition and source
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install application
RUN pip install --no-cache-dir .

# Default port
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn vg_mongo_proxy.main:app --host 0.0.0.0 --port ${PORT}"]
