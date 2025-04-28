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
docker-compose --version

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
ls -la Dockerfile docker-compose.yml supervisord.conf nginx.conf .env requirements.txt
```

#### 3.2 配置环境变量

检查并修改.env文件，特别是数据库连接信息：

```bash
# 使用服务器本机的数据库（如果PostgreSQL和MySQL安装在服务器上）
nano .env

# 修改数据库连接配置为：
# PG_HOST=localhost 或 PG_HOST=172.31.11.32
# MYSQL_HOST=localhost 或 MYSQL_HOST=172.31.11.32
```

#### 3.3 调整docker-compose.yml（如需使用服务器数据库）

如果您想使用服务器上已有的数据库，而不是Docker容器数据库：

```bash
nano docker-compose.yml

# 移除postgresql和mysql服务部分
# 移除volumes定义中的postgres_data和mysql_data
# 移除mcp服务的depends_on部分中对postgres和mysql的依赖
```

### 4. 准备目录和权限

```bash
# 创建日志和数据目录
mkdir -p logs data
chmod 777 logs data

# 确保Supervisor配置适合Linux环境
nano supervisord.conf

# 修改supervisord.conf中的路径，确保使用Linux路径格式
# 比如将文件目录从Windows格式：C:/Python/github/mcp/
# 改为Linux格式：/app/
```

### 5. 构建和启动服务

首先确保您的应用能够连接到现有的数据库容器网络：

```bash
# 查看现有网络
docker network ls

# 确认数据库容器所在的网络
docker inspect mcp-postgres-1 | grep -A 10 "Networks"
docker inspect mcp-mysql-1 | grep -A 10 "Networks"

# 如果需要，将应用添加到现有网络
# docker network connect <network_name> <container_name>
```

然后构建并启动服务：

```bash
# 构建Docker镜像并启动服务（后台运行）
docker-compose up -d --build

# 查看构建和启动过程
docker-compose logs -f

# 检查容器是否正常运行
docker-compose ps
```

### 6. 数据库初始化（可选，如果表已存在）

由于数据库容器(mcp-postgres-1和mcp-mysql-1)已经存在，并且数据表已经创建好，此步骤通常可以跳过。如果需要验证表是否存在，可以执行：

```bash
# 验证PostgreSQL表是否存在
docker exec mcp-postgres-1 psql -U postgres -c "\dt"

# 验证MySQL表是否存在
docker exec mcp-mysql-1 mysql -u root -proot_password news_content -e "SHOW TABLES"
```

如果需要重新创建表（谨慎操作，可能会丢失数据）：

```bash
# 初始化PostgreSQL数据库
docker-compose exec mcp python create_postgresql_tables.py

# 初始化MySQL数据库
docker-compose exec mcp python create_mysql_tables.py
```

### 7. 验证部署

```bash
# 访问API检查服务是否正常
curl http://localhost/

# 使用外部地址测试
curl http://47.86.227.107/

# 检查Supervisor管理的进程状态
docker-compose exec mcp supervisorctl status

# 检查Gunicorn日志
docker-compose exec mcp cat /app/logs/gunicorn_access.log
```

### 8. 测试工作流

使用API测试完整工作流：

```bash
# 启动扩展工作流任务，间隔120分钟
curl -X POST http://47.86.227.107/api/workflow/all -H "Content-Type: application/json" -d "{\"interval_minutes\": 120}"

# 查看工作流状态
docker-compose exec mcp supervisorctl status
docker-compose exec mcp cat /app/logs/workflow_stdout.log
```

## 维护操作

### 日常监控

```bash
# 检查容器状态
docker-compose ps

# 查看容器日志
docker-compose logs -f mcp

# 查看Nginx日志
docker-compose logs -f nginx

# 查看Gunicorn访问日志
docker exec -it $(docker-compose ps -q mcp) cat /app/logs/gunicorn_access.log

# 查看Gunicorn错误日志
docker exec -it $(docker-compose ps -q mcp) cat /app/logs/gunicorn_error.log

# 查看应用程序日志（根据您的logger_config.py配置）
docker exec -it $(docker-compose ps -q mcp) ls -la /app/logs/
docker exec -it $(docker-compose ps -q mcp) cat /app/logs/app.log  # 或其它应用程序日志文件

# 监控容器资源使用
docker stats
```

### 进程管理

```bash
# 查看Supervisor状态
docker-compose exec mcp supervisorctl status

# 重启应用程序
docker-compose exec mcp supervisorctl restart mcp

# 重启工作流程序
docker-compose exec mcp supervisorctl restart mcp_workflow

# 重新加载Supervisor配置
docker-compose exec mcp supervisorctl reload
```

### 数据备份

```bash
# 创建备份目录
mkdir -p /opt/mcp/backups

# 备份PostgreSQL数据库
docker-compose exec postgres pg_dump -U postgres postgres > /opt/mcp/backups/pg_backup_$(date +%Y%m%d).sql
# 或者直接在服务器上执行
pg_dump -h localhost -U postgres postgres > /opt/mcp/backups/pg_backup_$(date +%Y%m%d).sql

# 备份MySQL数据库
docker-compose exec mysql mysqldump -u root -proot_password news_content > /opt/mcp/backups/mysql_backup_$(date +%Y%m%d).sql
# 或者直接在服务器上执行
mysqldump -h localhost -u root -proot_password news_content > /opt/mcp/backups/mysql_backup_$(date +%Y%m%d).sql

# 设置自动备份（添加到crontab）
echo "0 2 * * * root pg_dump -h localhost -U postgres postgres > /opt/mcp/backups/pg_backup_\$(date +\%Y\%m\%d).sql" > /etc/cron.d/mcp_backup
echo "30 2 * * * root mysqldump -h localhost -u root -proot_password news_content > /opt/mcp/backups/mysql_backup_\$(date +\%Y\%m\%d).sql" >> /etc/cron.d/mcp_backup
chmod 644 /etc/cron.d/mcp_backup
```

### 更新部署

```bash
# 停止服务
docker-compose down

# 拉取最新代码
git pull

# 重新构建并启动服务
docker-compose up -d --build

# 查看更新后的日志
docker-compose logs -f
```

## 故障排除

### 1. 容器无法启动

```bash
# 检查Docker错误日志
docker-compose logs mcp

# 检查Docker系统日志
journalctl -u docker

# 确认容器是否有足够资源
docker stats

# 重置并重启服务
docker-compose down
docker system prune -f
docker-compose up -d
```

### 2. 数据库连接问题

```bash
# 检查数据库连接配置
cat .env

# 测试PostgreSQL连接
docker-compose exec mcp python -c "import psycopg2; conn=psycopg2.connect(dbname='postgres', user='postgres', host='localhost', password='root_password'); print('连接成功')"

# 测试MySQL连接
docker-compose exec mcp python -c "import mysql.connector; conn=mysql.connector.connect(host='localhost', user='root', password='root_password', database='news_content'); print('连接成功')"

# 检查服务器上的数据库服务是否运行
systemctl status postgresql
systemctl status mysql

# 确保数据库允许远程连接
# PostgreSQL: 检查pg_hba.conf
# MySQL: 检查my.cnf中的bind-address
```

### 3. API无法访问

```bash
# 检查Nginx配置
docker-compose exec nginx nginx -t

# 查看Nginx日志
docker-compose logs nginx

# 检查防火墙设置
iptables -L

# 测试内部服务连通性
docker-compose exec nginx curl http://mcp:5000/
```

### 4. Supervisor相关问题

```bash
# 检查Supervisor配置
docker-compose exec mcp cat /app/supervisord.conf

# 重载配置
docker-compose exec mcp supervisorctl reload

# 查看Supervisor管理的进程状态
docker-compose exec mcp supervisorctl status

# 重启Gunicorn
docker-compose exec mcp supervisorctl restart mcp

# 重启工作流进程
docker-compose exec mcp supervisorctl restart mcp_workflow

# 查看Supervisor日志
docker-compose exec mcp cat /app/logs/supervisord.log
```

### 5. 日志文件问题

```bash
# 查看日志目录中的文件
docker-compose exec mcp ls -la /app/logs/

# 检查日志目录权限
docker-compose exec mcp stat -c "%a %U:%G" /app/logs

# 如果日志目录权限不正确，可以修复
docker-compose exec mcp chown -R appuser:appuser /app/logs
docker-compose exec mcp chmod 755 /app/logs

# 手动创建日志目录（如果不存在）
docker-compose exec mcp mkdir -p /app/logs
```

### 6. Python版本问题

如果遇到Python版本兼容性问题：

```bash
# 查看容器内Python版本
docker-compose exec mcp python --version

# 修改Dockerfile中的Python基础镜像版本
# 编辑Dockerfile，修改为：
# FROM python:3.8-slim 或其他特定版本
nano Dockerfile

# 重新构建镜像
docker-compose down
docker-compose up -d --build
```

## 安全建议

1. 修改所有默认密码，特别是数据库密码
2. 实施HTTPS连接（考虑配置Let's Encrypt证书）
3. 定期更新Docker镜像和系统组件
4. 限制数据库端口访问，只对内部网络开放
5. 设置应用程序和数据库的定期备份策略
6. 实施日志轮转以避免磁盘空间耗尽
7. 监控系统资源使用情况，设置警报通知

## 系统监控设置

配置简单的系统监控：

```bash
# 安装基本监控工具
apt-get update
apt-get install -y htop iotop sysstat

# 配置基本资源监控
cat > /etc/cron.d/mcp_monitor << 'EOF'
*/5 * * * * root bash -c 'echo -e "\n\n===== $(date) =====\n" >> /opt/mcp/logs/system_monitor.log && free -m >> /opt/mcp/logs/system_monitor.log && echo -e "\n" >> /opt/mcp/logs/system_monitor.log && df -h >> /opt/mcp/logs/system_monitor.log && echo -e "\n" >> /opt/mcp/logs/system_monitor.log && docker stats --no-stream >> /opt/mcp/logs/system_monitor.log'
EOF
chmod 644 /etc/cron.d/mcp_monitor
```

## 联系方式

如有任何部署问题，请联系：<your-contact-info> 