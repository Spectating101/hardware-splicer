FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install only minimal runtime deps (no torch/opencv/etc).
COPY requirements.runtime.txt /app/requirements.runtime.txt
RUN pip install --no-cache-dir -r /app/requirements.runtime.txt

# Copy the application.
COPY . /app

ENV PORT=5000
EXPOSE 5000

CMD ["python", "api_server.py"]

