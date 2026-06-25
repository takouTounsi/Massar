FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app

COPY pyproject.toml /app/
COPY shared /app/shared
COPY services /app/services
COPY rules /app/rules
COPY data /app/data
RUN pip install --no-cache-dir -e .

EXPOSE 5061
CMD ["uvicorn", "services.classification_service.app.main:app", "--host", "0.0.0.0", "--port", "5061"]
