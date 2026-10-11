FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY analysis ./analysis
COPY api ./api
COPY dashboard ./dashboard
COPY ingest ./ingest
RUN useradd --create-home --uid 10001 appuser
USER appuser
EXPOSE 8000 8050
# Default: API with live ingestion. docker-compose.yml also runs the dashboard from this image.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
