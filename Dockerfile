FROM python:3.8-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    curl \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# 创建非root用户
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -s /bin/bash -m appuser

# 复制项目文件
COPY . /app/

# 确保日志目录存在并设置权限
RUN mkdir -p /app/logs /app/data && \
    chown -R appuser:appuser /app

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 安装生产级WSGI服务器
RUN pip install --no-cache-dir gunicorn

# 暴露端口
EXPOSE 5000

# 切换到非root用户
USER appuser

# 启动命令 - 使用supervisord
CMD ["supervisord", "-c", "/app/supervisord.conf"] 