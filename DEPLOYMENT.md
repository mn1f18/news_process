# MCP项目部署指南

本文档详细说明如何在Linux服务器(47.86.227.107)上使用Docker部署MCP项目。

## 前置条件

- Docker (版本 20.10+)
- Docker Compose (版本 2.0+)
- Git
- 已开放端口: 80 (HTTP), 3306 (MySQL), 5432 (PostgreSQL), 22 (SSH), 3389 (RDP)

## 部署步骤

### 1. 服务器环境准备

首先登录到服务器并检查环境：

```bash
# 登录到服务器
ssh root@47.86.227.107

# 检查Docker版本
docker --version
docker compose --version

# 检查Python版本
python3 --version

# 检查磁盘空间
df -h

# 确保时区设置正确
timedatectl
# 如果时区不是Asia/Shanghai，请设置
timedatectl set-timezone Asia/Shanghai
```

### 2. 克隆仓库

```bash
# 创建项目目录
mkdir -p /opt/mcp
cd /opt/mcp

# 克隆项目代码
git clone <your-repository-url> .
# 或者从本地上传文件
# 在本地执行：
# scp -r /path/to/local/mcp/* root@47.86.227.107:/opt/mcp/
```

### 3. 环境配置

#### 3.1 检查配置文件

确保以下关键文件存在：

```bash
ls -la Dockerfile docker-compose.yml nginx.conf .env requirements.txt
```

#### 3.2 配置环境变量

检查并修改.env文件，特别是数据库连接信息：

```bash
# 编辑.env文件
vim .env

# 修改数据库连接配置为：
PG_HOST=47.86.227.107
PG_PORT=5432
PG_USER=postgres
PG_PASSWORD=root_password
PG_DATABASE=postgres

MYSQL_HOST=47.86.227.107
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=root_password
MYSQL_DATABASE=news_content
```

### 4. 准备目录和权限

```bash
# 创建日志和数据目录
mkdir -p logs data
chmod 777 logs data
```

### 5. 构建和启动服务

首先创建Docker网络并连接数据库容器：

```bash
# 创建网络
docker network create mcp-network

# 将已有的数据库容器连接到网络
docker network connect mcp-network mcp-postgres-1
docker network connect mcp-network mcp-mysql-1
```

然后构建并启动服务：

```bash
# 构建Docker镜像并启动服务（后台运行）
docker compose up -d

# 检查容器是否正常运行
docker ps
```

如果应用容器未自动连接到网络，手动连接：

```bash
docker network connect mcp-network mcp-mcp-1
docker network connect mcp-network mcp-nginx-1
```

### 6. 检查数据库连接

确认应用能够连接到数据库：

```bash
# 查看应用日志，确认数据库连接成功
docker logs mcp-mcp-1

# 如果看到数据库连接错误，检查网络连接
docker network inspect mcp-network
```

### 7. 验证部署

```bash
# 访问API检查服务是否正常
curl http://localhost/

# 使用外部地址测试
curl http://47.86.227.107/
```

### 8. 测试工作流

使用API测试完整工作流：

```bash
# 启动扩展工作流任务，间隔120分钟
curl -X POST http://47.86.227.107/api/workflow/all -H "Content-Type: application/json" -d "{\"interval_minutes\": 120}"

# 查看工作流状态
curl http://47.86.227.107/api/workflows
```

## 维护操作

### 日常监控

```bash
# 检查容器状态
docker ps

# 查看容器日志
docker logs -f mcp-mcp-1

# 查看Nginx日志
docker logs -f mcp-nginx-1

# 查看应用程序日志
docker exec -it mcp-mcp-1 ls -la /app/logs/
docker exec -it mcp-mcp-1 cat /app/logs/app_*.log

# 监控容器资源使用
docker stats
```

### 工作流管理

```bash
# 查看调度器任务
curl http://localhost/api/scheduler/jobs

# 暂停任务
curl -X POST http://localhost/api/scheduler/pause/<job_id>

# 恢复任务
curl -X POST http://localhost/api/scheduler/resume/<job_id>

# 移除任务
curl -X POST http://localhost/api/scheduler/remove/<job_id>
```

### 数据备份

```bash
# 创建备份目录
mkdir -p /opt/mcp/backups

# 备份PostgreSQL数据库
docker exec mcp-postgres-1 pg_dump -U postgres postgres > /opt/mcp/backups/pg_backup_$(date +%Y%m%d).sql

# 备份MySQL数据库
docker exec mcp-mysql-1 mysqldump -u root -proot_password news_content > /opt/mcp/backups/mysql_backup_$(date +%Y%m%d).sql

# 设置自动备份（添加到crontab）
echo "0 2 * * * root pg_dump -h localhost -U postgres postgres > /opt/mcp/backups/pg_backup_\$(date +\%Y\%m\%d).sql" > /etc/cron.d/mcp_backup
echo "30 2 * * * root mysqldump -h localhost -u root -proot_password news_content > /opt/mcp/backups/mysql_backup_\$(date +\%Y\%m\%d).sql" >> /etc/cron.d/mcp_backup
chmod 644 /etc/cron.d/mcp_backup
```

### 更新部署

```bash
# 停止服务
docker compose down

# 拉取最新代码
git pull

# 重新构建并启动服务
docker compose up -d --build

# 查看更新后的日志
docker logs -f mcp-mcp-1
```

## 故障排除

### 1. 容器无法启动

```bash
# 检查Docker错误日志
docker logs mcp-mcp-1

# 检查Docker系统日志
journalctl -u docker

# 重置并重启服务
docker compose down
docker compose up -d
```

### 2. 数据库连接问题

```bash
# 检查数据库连接配置
cat .env

# 确保使用正确的主机IP
PG_HOST=47.86.227.107
MYSQL_HOST=47.86.227.107

# 确保所有容器连接到同一网络
docker network inspect mcp-network

# 重新连接容器到网络
docker network connect mcp-network mcp-postgres-1
docker network connect mcp-network mcp-mysql-1
docker network connect mcp-network mcp-mcp-1
docker network connect mcp-network mcp-nginx-1

# 重建容器
docker compose down
docker compose up -d
```

### 3. API无法访问

```bash
# 检查Nginx配置
docker exec mcp-nginx-1 nginx -t

# 查看Nginx日志
docker logs mcp-nginx-1

# 测试内部服务连通性
docker exec mcp-nginx-1 curl http://mcp-mcp-1:5000/
```

### 4. API库版本不兼容

如果出现API错误（例如"unrecognized_keys"）：

```bash
# 检查firecrawl库版本
docker exec mcp-mcp-1 pip show firecrawl

# 修改requirements.txt锁定版本
# 添加: firecrawl==1.15.0

# 重新安装兼容版本
docker exec mcp-mcp-1 pip install firecrawl==1.15.0

# 或重新构建容器
docker compose down
docker compose build --no-cache
docker compose up -d
```

### 5. 日志文件问题

```bash
# 查看日志目录中的文件
docker exec mcp-mcp-1 ls -la /app/logs/

# 确保日志目录存在且有写入权限
docker exec mcp-mcp-1 mkdir -p /app/logs
docker exec mcp-mcp-1 chmod 777 /app/logs
```

## 安全建议

1. 修改所有默认密码，特别是数据库密码
2. 实施HTTPS连接（考虑配置Let's Encrypt证书）
3. 定期更新Docker镜像和系统组件
4. 限制数据库端口访问，只对内部网络开放
5. 设置应用程序和数据库的定期备份策略
6. 实施日志轮转以避免磁盘空间耗尽
7. 监控系统资源使用情况，设置警报通知