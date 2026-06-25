FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app

COPY pyproject.toml /app/
COPY alembic.ini /app/alembic.ini
COPY shared /app/shared
COPY services /app/services
COPY rules /app/rules
COPY data /app/data
RUN pip install --no-cache-dir -e .

EXPOSE 5063
CMD ["uvicorn", "services.evaluation_service.app.main:app", "--host", "0.0.0.0", "--port", "5063"]
