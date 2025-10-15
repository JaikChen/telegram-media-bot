# 使用官方 Python 基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝项目文件
COPY . .

# 设置环境变量（可在 docker-compose.yml 或 .env 覆盖）
ENV PYTHONUNBUFFERED=1

# 启动 Bot
CMD ["python", "main.py"]