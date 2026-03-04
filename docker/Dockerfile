FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    chromium \
    xvfb \
    git \
    python3-tk \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8765
CMD ["python", "main.py"]
