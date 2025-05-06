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

# 添加API域名到hosts文件以解决DNS解析问题
RUN echo "34.111.212.187 api.firecrawl.dev" >> /etc/hosts

# 暴露端口
EXPOSE 5000

# 切换到非root用户 - 暂时注释掉以解决权限问题
# USER appuser

# 原来的启动命令，已被docker-compose.yml中的command覆盖
# CMD ["supervisord", "-c", "/app/supervisord.conf"]