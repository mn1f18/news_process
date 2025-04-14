# 新闻监控与分析系统

这是一个集成的新闻监控与分析系统，用于自动抓取、验证和分析新闻链接。系统通过工作流引擎和状态管理机制，将不同组件连接成一个完整的处理管道。

## 系统架构

系统由以下主要组件构成：

1. **主页抓取器** (步骤 1)：
   - 从Excel文件中读取主页URL
   - 定期抓取主页链接并与历史记录比较
   - 发现新链接并保存

2. **链接分析器** (步骤 2)：
   - 对链接进行分析以确定是否与目标主题相关
   - 使用百炼智能体进行内容相关性判断
   - 记录分析结果和链接状态

3. **深度内容抓取器** (步骤 3)：
   - 对步骤2筛选出的有效链接进行深度内容抓取
   - 使用DashScope API提取页面内容
   - 保存完整的页面内容用于后续分析

4. **工作流管理器**：
   - 协调三个步骤之间的数据流
   - 维护状态管理系统
   - 提供重试和错误恢复机制

5. **API服务器**：
   - 提供REST API接口供外部系统调用
   - 支持各种操作如启动抓取、分析链接等
   - 允许查询工作流和链接状态

## 数据流

系统支持三种主要的数据流路径：

1. **步骤1**: 主页抓取 → 新链接保存
2. **步骤1+2**: 主页抓取 → 新链接发现 → 链接分析 → 结果存储
3. **步骤1+2+3**: 主页抓取 → 新链接发现 → 链接分析 → 有效链接深度抓取 → 内容存储

## 安装和配置

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 配置环境变量：
在项目根目录创建 `.env` 文件，包含以下配置：
```
DASHSCOPE_API_KEY=your_api_key
BAILIAN_APP_ID=your_app_id
FIRECRAWL_API_KEY=your_api_key
LINK_ANALYZER_APP_ID=your_app_id
```

3. 准备Excel文件：
创建 `testhomepage.xlsx` 文件，包含以下列：
- link: 主页URL
- 备注: 备注信息
- 来源: 来源信息

## 运行系统

### 命令行模式

1. 运行完整工作流（步骤1+2）：
```bash
python app.py run-workflow
```

2. 只分析最新抓取的链接（步骤2）：
```bash
python app.py analyze-latest [max_links]
```

3. 处理有效链接进行深度分析（步骤3）：
```bash
python app.py process-valid [max_links]
```

4. 运行完整扩展工作流（步骤1+2+3）：
```bash
python app.py extended-workflow
```

### API服务器模式

启动API服务器：
```bash
python app.py
```

默认情况下，服务器将在 http://127.0.0.1:5000 上运行。

## API端点详细说明

### 1. 主页抓取 (步骤1)

**端点**: `/api/step1`  
**方法**: POST  
**功能**: 从配置的Excel文件中读取主页URL，抓取这些页面上的链接，并与历史记录比较找出新链接

**生成的数据文件**:
- `scrape_link_cache.json`: 所有历史链接的缓存
- `scrape_new_links.json`: 按时间戳组织的新发现链接

**示例请求**:
```bash
curl -X POST http://localhost:5000/api/step1
```

**示例响应**:
```json
{
  "status": "accepted",
  "workflow_id": "workflow_step1_20250414153034",
  "message": "Homepage scraping task has been queued"
}
```

### 2. 指定链接分析 (步骤2)

**端点**: `/api/step2`  
**方法**: POST  
**功能**: 分析提供的链接列表，确定每个链接是否与目标主题相关

**请求参数**:
```json
{
  "links": [
    {
      "link": "https://example.com/news",
      "source": "Example News",
      "note": "Example homepage"
    }
  ]
}
```

**生成的数据文件**:
- `valid_links.json`: 有效链接及分析结果
- `invalid_links.json`: 无效链接及分析结果
- `analysis_results/analysis_{workflow_id}.json`: 完整分析结果汇总

**示例请求**:
```bash
curl -X POST -H "Content-Type: application/json" -d '{"links":[{"link":"https://example.com/news","source":"Example News","note":"Example homepage"}]}' http://localhost:5000/api/step2
```

### 3. 分析最新抓取的链接 (步骤2)

**端点**: `/api/step2/latest`  
**方法**: POST  
**功能**: 获取步骤1最近抓取的链接，并进行分析判断

**请求参数**:
```json
{
  "max_links": 50  // 可选，默认分析50个链接
}
```

**生成的数据文件**:
- `valid_links.json`: 有效链接及分析结果
- `invalid_links.json`: 无效链接及分析结果
- `analysis_results/analysis_{workflow_id}.json`: 分析结果汇总

**示例请求**:
```bash
curl -X POST http://localhost:5000/api/step2/latest
curl -X POST -H "Content-Type: application/json" -d '{"max_links": 100}' http://localhost:5000/api/step2/latest
```

### 4. 处理有效链接 (步骤3)

**端点**: `/api/step3`  
**方法**: POST  
**功能**: 处理步骤2筛选出的有效链接，进行内容抓取和深度分析

**请求参数**:
```json
{
  "max_links": 10,  // 可选，默认处理10个链接
  "links": ["https://example.com/news1", "https://example.com/news2"]  // 可选，自定义链接列表
}
```

**生成的数据文件**:
- `content/`: 目录，包含每个链接的抓取内容
- `content/link_{workflow_id}_{i}.txt`: 每个链接的抓取结果
- `summaries/summary_{workflow_id}.json`: 处理结果摘要

**示例请求**:
```bash
curl -X POST http://localhost:5000/api/step3
curl -X POST -H "Content-Type: application/json" -d '{"max_links": 5}' http://localhost:5000/api/step3
```

### 5. 完整工作流 (步骤1+2)

**端点**: `/api/workflow/step1to2`  
**方法**: POST  
**功能**: 运行完整工作流，包括抓取主页和分析链接

**生成的数据文件**:
- 步骤1和步骤2中提到的所有文件

**示例请求**:
```bash
curl -X POST http://localhost:5000/api/workflow/step1to2
```

### 6. 扩展工作流 (步骤1+2+3)

**端点**: `/api/workflow/all`  
**方法**: POST  
**功能**: 运行完整扩展工作流，包括抓取主页、分析链接和处理有效链接

**生成的数据文件**:
- 步骤1、步骤2和步骤3中提到的所有文件

**示例请求**:
```bash
curl -X POST http://localhost:5000/api/workflow/all
```

### 7. 查询工作流状态

**端点**: `/api/workflow/{workflow_id}`  
**方法**: GET  
**功能**: 获取指定工作流的状态和历史

**生成的数据文件**: 无（只读取现有数据）

**示例请求**:
```bash
curl http://localhost:5000/api/workflow/workflow_20250414153034
```

### 8. 查询所有工作流

**端点**: `/api/workflows`  
**方法**: GET  
**功能**: 获取所有工作流的状态，可选根据状态筛选

**查询参数**:
- `status`: 可选，根据状态筛选，如 `COMPLETED`

**生成的数据文件**: 无（只读取现有数据）

**示例请求**:
```bash
curl http://localhost:5000/api/workflows
curl http://localhost:5000/api/workflows?status=COMPLETED
```

### 9. 获取链接状态

**端点**: `/api/link/{link_id}`  
**方法**: GET  
**功能**: 获取特定链接的分析状态和结果

**生成的数据文件**: 无（只读取现有数据）

**示例请求**:
```bash
curl http://localhost:5000/api/link/batch_20250414153034_1
```

### 10. 重新分析失败的链接

**端点**: `/api/reanalyze`  
**方法**: POST  
**功能**: 重新分析之前分析失败的链接

**生成的数据文件**:
- 更新 `valid_links.json` 或 `invalid_links.json`
- 生成新的 `analysis_results_workflow_reanalyze_{timestamp}.json`

**示例请求**:
```bash
curl -X POST http://localhost:5000/api/reanalyze
```

## 数据文件详解

系统采用按功能划分的目录结构存储数据：

```
├── scrape_link_cache.json      # 所有历史抓取链接的缓存
├── scrape_new_links.json       # 按时间戳组织的新发现链接
├── archives/                   # 归档的历史数据
│
├── valid_links.json           # 被判定为有效的链接及分析理由
├── invalid_links.json         # 被判定为无效的链接及分析理由
├── analysis_results/          # 分析结果文件夹
│   └── analysis_{workflow_id}.json  # 各工作流分析结果
│
├── content/                   # 抓取的内容 
│   └── link_{workflow_id}_{i}.txt   # 单个链接抓取结果
└── summaries/                 # 分析摘要
    └── summary_{workflow_id}.json   # 工作流结果摘要
```

这种结构使各步骤的数据明确分离，便于管理和后续扩展。各文件的具体功能：

1. **步骤1 (主页抓取)**:
   - `scrape_link_cache.json`: 所有历史抓取链接的缓存
   - `scrape_new_links.json`: 按时间戳组织的新发现链接
   - `archives/`: 旧链接数据归档目录，包含按日期命名的归档文件

2. **步骤2 (链接分析)**:
   - `valid_links.json`: 被判定为有效的链接及分析理由
   - `invalid_links.json`: 被判定为无效的链接及分析理由
   - `analysis_results/analysis_{workflow_id}.json`: 每个工作流的完整分析结果

3. **步骤3 (深度内容抓取)**:
   - `content/link_{workflow_id}_{i}.txt`: 每个链接的内容抓取结果
   - `summaries/summary_{workflow_id}.json`: 步骤3处理结果摘要，包含成功/失败统计

