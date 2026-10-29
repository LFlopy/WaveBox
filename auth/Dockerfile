FROM python:3.14-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY auth/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY auth/ .
COPY python-backend/import_tracks.py python-backend/models.py /python-backend/

EXPOSE 8000
