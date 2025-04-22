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

### 技术栈

- **后端**: Flask，Python 3.8+
- **数据库**: 
  - PostgreSQL: 存储链接分析和工作流数据
  - MySQL: 存储内容结果和网站配置
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

### 命令行使用

```bash
# 运行完整工作流 (步骤1+2)
python app.py run-workflow

# 分析最新抓取的链接 (最多50个)
python app.py analyze-latest 50

# 处理有效链接 (最多10个)
python app.py process-valid 10

# 运行完整扩展工作流 (步骤1+2+3)
python app.py extended-workflow
```

## 数据库结构

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
├── db_utils.py                 # 数据库操作工具
├── pg_connection.py            # PostgreSQL连接管理
├── config.py                   # 配置和环境变量加载
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

### PostgreSQL连接管理 (pg_connection.py)
提供稳定的PostgreSQL连接上下文管理器，自动处理连接获取、事务管理和连接释放。

### MySQL连接管理 (db_utils.py中的mysql_connection类)
提供可靠的MySQL连接上下文管理器，支持自动重试和错误恢复。

## 最近更新

- **数据库连接改进**: 增强了PostgreSQL和MySQL连接的稳定性和错误恢复能力
- **Step3处理优化**: 使用实际API调用替代模拟数据，改进了内容保存到MySQL的流程
- **表结构规范化**: 确保所有数据库操作使用正确的表名(news_content.step3_content)
- **错误处理增强**: 在整个流程中添加了更详细的错误日志和重试机制
- **配置和环境变量**: 统一管理配置和环境变量，确保安全性

## 注意事项

- 系统依赖外部API，请确保API密钥有效且有足够的调用额度
- 步骤1(主页抓取)包含15秒等待时间，以避免API请求过于频繁
- 定期检查日志文件，特别是db_utils相关日志，确保数据库连接正常
- 所有关键数据存储在数据库中，不依赖本地文件
- PostgreSQL和MySQL服务器必须可访问且正常运行

## 许可

[指定许可证信息] 