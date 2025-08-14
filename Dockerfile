FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN alembic upgrade head

ENV PORT=8000
EXPOSE $PORT

CMD ["sh", "-c", "uvicorn src.app:app --host 0.0.0.0 --port $PORT"]

