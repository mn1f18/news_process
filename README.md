# 新闻内容处理系统 (MCP)

一个基于Python、Flask和双数据库的系统，用于自动化新闻内容处理和分析的ETL流程。

## 项目概述

本系统是一个完整的ETL(Extract-Transform-Load)管道，用于:
1. 从已配置的新闻网站抓取内容
2. 分析链接有效性
3. 抓取和处理有效链接的内容
4. 存储分析结果到数据库中

系统由三个主要步骤组成，每个步骤可以独立运行，也可以作为完整工作流一起运行。所有数据通过PostgreSQL和MySQL数据库存储和共享，不依赖本地文件存储。

## 系统架构

### 组件结构

- **步骤1 (Homepage Scraping)**: 抓取配置的主页并发现新链接，使用FireCrawl API
- **步骤2 (Link Analysis)**: 分析链接有效性，使用百炼应用判断链接是否有价值
- **步骤3 (Content Processing)**: 处理有效链接的内容，使用SDK进行内容抓取和解析
- **工作流管理**: 协调各步骤间的数据流转，提供状态跟踪
- **REST API**: 提供HTTP接口访问各功能，支持异步任务处理
- **调度系统**: 使用APScheduler库实现可靠的定时任务调度，支持精确的时间间隔执行
- **备用内容抓取**: 使用firecrawl_news_crawler.py作为备用抓取方案，当主要方法失败时自动切换

### 技术栈

- **后端**: Flask，Python 3.8+
- **数据库**: 
  - PostgreSQL: 存储链接分析和工作流数据
  - MySQL: 存储内容结果和网站配置
- **任务调度**: APScheduler 3.9+
- **外部API**:
  - DashScope: 用于AI内容分析
  - FireCrawl: 用于网页抓取
  - 百炼应用: 用于链接分析和内容处理

### 数据流

1. 从MySQL数据库读取主页URL配置
2. 抓取主页，发现新链接，保存到PostgreSQL
3. 链接分析确定哪些链接值得进一步处理
4. 内容抓取和处理，结果保存到MySQL的news_content.step3_content表

## 安装和部署

### 需求

- Python 3.8+
- PostgreSQL 13+
- MySQL 8+
- API密钥 (DashScope, FireCrawl, 百炼)

### 安装步骤

1. 克隆仓库
```bash
git clone <repository-url>
cd mcp
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 配置环境变量 (`.env` 文件)
```
DASHSCOPE_API_KEY=your_dashscope_key
BAILIAN_APP_ID=your_bailian_app_id
FIRECRAWL_API_KEY=your_firecrawl_key
LINK_ANALYZER_APP_ID=your_link_analyzer_app_id
MCP_BACKUP_APP_ID=your_mcp_backup_app_id

PG_HOST=your_postgres_host
PG_PORT=5432
PG_USER=postgres
PG_PASSWORD=your_password
PG_DATABASE=postgres

MYSQL_HOST=your_mysql_host
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=news_content
```

4. 创建数据库表
```bash
python create_postgresql_tables.py
python create_mysql_tables.py
```

5. 启动服务器
```bash
python app.py
```

## 使用方法

### API 端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/step1` | POST | 运行步骤1 (主页抓取) |
| `/api/step2` | POST | 运行步骤2 (链接分析) |
| `/api/step2/latest` | POST | 分析最新抓取的链接 |
| `/api/step3` | POST | 运行步骤3 (内容处理) |
| `/api/workflow/step1to2` | POST | 运行完整工作流 (步骤1+2) |
| `/api/workflow/all` | POST | 运行完整工作流 (步骤1+2+3) |
| `/api/workflow/<workflow_id>` | GET | 获取工作流状态 |
| `/api/workflows` | GET | 获取所有工作流状态 |
| `/api/link/<link_id>` | GET | 获取链接状态 |
| `/api/reanalyze` | POST | 重新分析失败的链接 |
| `/api/scheduler/jobs` | GET | 获取所有调度任务 |
| `/api/scheduler/pause/<job_id>` | POST | 暂停指定的调度任务 |
| `/api/scheduler/resume/<job_id>` | POST | 恢复指定的调度任务 |
| `/api/scheduler/remove/<job_id>` | POST | 删除指定的调度任务 |

### 定时运行

系统支持基于APScheduler的可靠定时任务功能，可以通过API设置运行间隔：

```bash
# 每60分钟运行一次完整工作流
curl -X POST http://localhost:5000/api/workflow/all -H "Content-Type: application/json" -d '{"interval_minutes": 60}'

# 只运行一次完整工作流
curl -X POST http://localhost:5000/api/workflow/all
```

#### 定时任务管理

系统提供了完整的定时任务管理API：

```bash
# 查看所有定时任务
curl -X GET http://localhost:5000/api/scheduler/jobs

# 暂停指定任务
curl -X POST http://localhost:5000/api/scheduler/pause/<job_id>

# 恢复指定任务
curl -X POST http://localhost:5000/api/scheduler/resume/<job_id>

# 删除指定任务
curl -X POST http://localhost:5000/api/scheduler/remove/<job_id>
```

#### 定时任务特性

- **精确调度**: 基于APScheduler的调度系统确保任务按照指定的时间间隔准确执行
- **任务排队**: 如果当前任务运行时间超过调度间隔，系统会等待当前任务完成后再执行下一个任务
- **错误恢复**: 即使任务执行失败，调度系统仍会在下一个时间点尝试再次执行
- **持久化**: 调度信息存储在内存中，服务重启后需要重新设置

### 日志系统

系统使用分模块的日志记录：

- `step1_*.log`: 主页抓取日志
- `step2_*.log`: 链接分析日志
- `step3_*.log`: 内容处理日志
- `app_*.log`: API服务日志

日志特点：
- 按日期自动轮转
- 只保留当天日志
- 支持UTF-8编码
- 同时输出到文件和控制台
- **进程ID隔离**: 日志文件名格式为`模块名_日期_pid进程ID.log`，确保不同进程写入不同日志文件
- **文件锁冲突避免**: 使用进程ID命名防止多进程同时写入同一文件导致的锁冲突
- **安全日志轮转**: 自定义`SafeRotatingFileHandler`处理器，避免日志轮转过程中的文件锁定问题

### 数据库结构

系统使用两个数据库来存储不同类型的数据：
1. PostgreSQL 用于存储工作流状态和链接分析数据
2. MySQL 用于存储内容处理结果和主页配置

### PostgreSQL 表
PostgreSQL服务器运行在 47.86.227.107:5432，使用postgres/root_password认证。

- **step0_workflows**: 工作流状态跟踪
  ```sql
  CREATE TABLE step0_workflows (
      workflow_id VARCHAR(50) PRIMARY KEY,
      created_at TIMESTAMP NOT NULL,
      updated_at TIMESTAMP NOT NULL,
      current_status VARCHAR(20) NOT NULL,
      details JSONB
  );
  ```

- **step0_workflow_history**: 工作流状态历史记录
  ```sql
  CREATE TABLE step0_workflow_history (
      id SERIAL PRIMARY KEY,
      workflow_id VARCHAR(50) REFERENCES step0_workflows(workflow_id),
      status VARCHAR(20) NOT NULL,
      timestamp TIMESTAMP NOT NULL,
      details JSONB,
      error TEXT
  );
  ```

- **step1_link_cache**: 历史链接缓存
  ```sql
  CREATE TABLE step1_link_cache (
      homepage_url TEXT NOT NULL,
      link TEXT NOT NULL,
      created_at TIMESTAMP NOT NULL,
      PRIMARY KEY (homepage_url, link)
  );
  ```

- **step1_new_links**: 新发现的链接
  ```sql
  CREATE TABLE step1_new_links (
      id SERIAL PRIMARY KEY,
      timestamp TIMESTAMP NOT NULL,
      homepage_url TEXT NOT NULL,
      link TEXT NOT NULL,
      source TEXT,
      note TEXT,
      batch_id VARCHAR(50) NOT NULL,
      created_at TIMESTAMP NOT NULL
  );
  ```

- **step2_link_analysis**: 链接分析结果
  ```sql
  CREATE TABLE step2_link_analysis (
      link_id VARCHAR(50) PRIMARY KEY,
      link TEXT NOT NULL,
      is_valid BOOLEAN NOT NULL,
      analysis_result JSONB,
      confidence FLOAT,
      reason TEXT,
      workflow_id VARCHAR(50) REFERENCES step0_workflows(workflow_id),
      created_at TIMESTAMP NOT NULL,
      updated_at TIMESTAMP NOT NULL
  );
  ```

- **step2_analysis_results**: 批量分析结果
  ```sql
  CREATE TABLE step2_analysis_results (
      id SERIAL PRIMARY KEY,
      workflow_id VARCHAR(50) REFERENCES step0_workflows(workflow_id),
      batch_id VARCHAR(50) NOT NULL,
      analysis_data JSONB NOT NULL,
      created_at TIMESTAMP NOT NULL
  );
  ```

### MySQL 表
MySQL服务器运行在 47.86.227.107:3306，使用root/root_password认证。

- **news_content.step3_content**: 内容处理结果
  ```sql
  CREATE TABLE step3_content (
      id INT AUTO_INCREMENT PRIMARY KEY,
      link_id VARCHAR(50) NOT NULL,
      title TEXT,
      content LONGTEXT,
      event_tags JSON,
      space_tags JSON,
      cat_tags JSON,
      impact_factors JSON,
      publish_time DATE,
      importance VARCHAR(20),
      state JSON,
      source_note TEXT,
      homepage_url VARCHAR(255),
      workflow_id VARCHAR(50),
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE KEY (link_id)
  );
  ```

- **homepage_urls**: 要抓取的主页配置
  ```sql
  CREATE TABLE homepage_urls (
      id INT AUTO_INCREMENT PRIMARY KEY,
      link VARCHAR(255) NOT NULL,
      source VARCHAR(100),
      note TEXT,
      active BOOLEAN NOT NULL DEFAULT TRUE,
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      UNIQUE KEY (link)
  );
  ```

## 目录结构

```
/
├── app.py                      # 主应用文件和REST API
├── step_1_homepage_scrape.py   # 步骤1实现 - 主页抓取
├── step2_link_test.py          # 步骤2实现 - 链接分析
├── step_3_scrape_test_sdk.py   # 步骤3实现 - 内容抓取和处理
├── firecrawl_news_crawler.py   # FireCrawl新闻爬取组件，用作备用方案
├── db_utils.py                 # 数据库操作工具
├── pg_connection.py            # PostgreSQL连接管理
├── config.py                   # 配置和环境变量加载
├── logger_config.py            # 日志配置模块
├── process_valid_links_to_mysql.py # 处理有效链接的独立脚本
├── create_postgresql_tables.py # PostgreSQL表创建脚本 
├── create_mysql_tables.py      # MySQL表创建脚本
├── import_homepage_excel.py    # 从Excel导入主页URL
├── .env                        # 环境变量
├── requirements.txt            # 依赖包
├── logs/                       # 日志目录
├── data/                       # 数据目录
└── archives/                   # 存档文件
```

## 数据库连接特性

系统实现了强大的数据库连接管理机制：

1. **连接池**: 使用连接池管理数据库连接，提高性能
2. **自动重试**: 连接失败时自动重试，最多重试3次
3. **错误恢复**: 包含完整的错误处理和日志记录
4. **事务管理**: 自动处理事务提交和回滚
5. **资源释放**: 确保所有连接都被正确关闭
6. **连接池健康检查**: 定期检查连接池状态，确保连接有效
7. **自动重连机制**: 在连接失效或连接池为None时自动重新初始化连接池

### PostgreSQL连接管理 (pg_connection.py)
提供稳定的PostgreSQL连接上下文管理器，自动处理连接获取、事务管理和连接释放。

### MySQL连接管理 (db_utils.py中的mysql_connection类)
提供可靠的MySQL连接上下文管理器，支持自动重试和错误恢复，能够处理连接池为None的异常情况。

### 数据库连接故障防范
- 开始关键操作前检查连接池状态
- 连接超时自动重连
- 网络中断后自动恢复
- 长时间运行任务的连接保持

## 最近更新

- **添加FireCrawl备用爬取机制**: 新增`firecrawl_news_crawler.py`组件作为备用内容爬取方案，当主要爬取方法失败时自动切换
- **更新环境变量配置**: 添加了`MCP_BACKUP_APP_ID`环境变量，用于备用内容处理
- **Step3失败处理流程增强**: 改进了Step3中的失败处理逻辑，主方法失败后自动调用FireCrawl备用方案
- **日志输出优化**: 减少了数据库URL列表等非关键信息的日志输出，提高日志可读性
- **重试机制调整**: 将Step3的最大重试次数从2次调整为1次，加快备用方案的启用
- **内容分析流程优化**: 使用专门的新闻爬取组件提高内容提取准确性
- **Step3重试机制增强**: 实现了更强大的重试机制，针对不同错误类型自动选择合适的处理方案
- **日志系统进程隔离**: 使用进程ID作为日志文件名的一部分，确保同一进程使用同一个日志文件，防止多进程并发写入冲突
- **数据库连接池健康管理**: 增加连接池健康检查和自修复机制，自动处理连接失效情况
- **添加APScheduler调度系统**: 实现了基于APScheduler的可靠定时任务系统，支持精确时间间隔执行
- **定时任务管理API**: 新增API接口用于查看、暂停、恢复和删除定时任务
- **添加影响因素字段**: 添加impact_factors字段，用于存储1-3个最相关的影响因素
- **日志系统优化**: 添加日志轮转和模块化日志记录
- **定时运行功能**: 支持通过API设置工作流运行间隔
- **数据库连接改进**: 增强了PostgreSQL和MySQL连接的稳定性和错误恢复能力
- **Step3处理优化**: 使用实际API调用替代模拟数据，改进了内容保存到MySQL的流程
- **表结构规范化**: 确保所有数据库操作使用正确的表名(news_content.step3_content)
- **错误处理增强**: 在整个流程中添加了更详细的错误日志和重试机制
- **配置和环境变量**: 统一管理配置和环境变量，确保安全性

## 注意事项

- 系统依赖外部API，请确保API密钥有效且有足够的调用额度
- 步骤1(主页抓取)包含2秒等待时间，以避免API请求过于频繁
- 定期检查日志文件，特别是db_utils相关日志，确保数据库连接正常
- 所有关键数据存储在数据库中，不依赖本地文件
- PostgreSQL和MySQL服务器必须可访问且正常运行
- 如果定时任务运行时间超过设定间隔，系统会等待当前任务完成后再执行下一次任务
