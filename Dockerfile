FROM python:3.10-slim

WORKDIR /app

# 安装 poetry
RUN pip install poetry

# 复制项目文件
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root

COPY ema_volume_monitor.py .
COPY .env .

CMD ["poetry", "run", "python", "ema_volume_monitor.py"]