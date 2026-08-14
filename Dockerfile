# Insight Web 平台镜像
FROM python:3.12-slim

# matplotlib 中文渲染 + 时区数据
RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-noto-cjk \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "web.server"]
