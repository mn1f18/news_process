数据库表结构梳理：

mysql:
47.86.227.107 
3306
root
root_password

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

postgresql:
47.86.227.107
5432
postgres
root_password

CREATE TABLE step0_workflows (
    workflow_id VARCHAR(50) PRIMARY KEY,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    current_status VARCHAR(20) NOT NULL,
    details JSONB
);

CREATE TABLE step0_workflow_history (
    id SERIAL PRIMARY KEY,
    workflow_id VARCHAR(50) REFERENCES step0_workflows(workflow_id),
    status VARCHAR(20) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    details JSONB,
    error TEXT
);

CREATE TABLE step1_link_cache (
    homepage_url TEXT NOT NULL,
    link TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    PRIMARY KEY (homepage_url, link)
);

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

CREATE TABLE step2_analysis_results (
    id SERIAL PRIMARY KEY,
    workflow_id VARCHAR(50) REFERENCES step0_workflows(workflow_id),
    batch_id VARCHAR(50) NOT NULL,
    analysis_data JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL
);