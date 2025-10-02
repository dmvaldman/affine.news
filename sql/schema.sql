-- Neon schema for Affine News

CREATE TABLE IF NOT EXISTS paper (
    uuid TEXT PRIMARY KEY,
    url TEXT UNIQUE,
    country TEXT,
    ISO TEXT,
    lang TEXT,
    whitelist TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS category_set (
    paper_uuid TEXT,
    url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY(paper_uuid) REFERENCES paper(uuid) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS crawl (
    uuid TEXT PRIMARY KEY,
    created_at TIMESTAMP,
    status INTEGER,
    max_articles INTEGER,
    paper_uuid TEXT,
    FOREIGN KEY(paper_uuid) REFERENCES paper(uuid) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS article (
    url TEXT PRIMARY KEY,
    img_url TEXT,
    title TEXT,
    title_translated TEXT,
    lang TEXT,
    publish_at TIMESTAMP,
    paper_uuid TEXT,
    crawl_uuid TEXT,
    title_embedding VECTOR(768),
    FOREIGN KEY(paper_uuid) REFERENCES paper(uuid) ON DELETE CASCADE,
    FOREIGN KEY(crawl_uuid) REFERENCES crawl(uuid),
);

CREATE TABLE IF NOT EXISTS daily_topics (
    id SERIAL PRIMARY KEY,
    topic TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Article-level country references (raw data)
CREATE TABLE IF NOT EXISTS article_country_reference (
    article_url TEXT REFERENCES article(url) ON DELETE CASCADE,
    source_country_iso CHAR(3) NOT NULL,
    target_country_iso CHAR(3) NOT NULL,
    favorability SMALLINT NOT NULL, -- -1, 0, 1
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (article_url, target_country_iso)
);

-- Materialized view for aggregated country comparison stats
CREATE MATERIALIZED VIEW IF NOT EXISTS country_comparisons AS
SELECT
    source_country_iso,
    target_country_iso,
    SUM(CASE WHEN favorability = 1 THEN 1 ELSE 0 END)::INT as positive_count,
    SUM(CASE WHEN favorability = -1 THEN 1 ELSE 0 END)::INT as negative_count,
    SUM(CASE WHEN favorability = 0 THEN 1 ELSE 0 END)::INT as neutral_count,
    MAX(created_at) as updated_at
FROM article_country_reference
GROUP BY source_country_iso, target_country_iso;

-- Index on the materialized view
CREATE UNIQUE INDEX IF NOT EXISTS idx_country_comp_pair ON country_comparisons (source_country_iso, target_country_iso);
CREATE INDEX IF NOT EXISTS idx_country_comp_source ON country_comparisons (source_country_iso);
CREATE INDEX IF NOT EXISTS idx_country_comp_target ON country_comparisons (target_country_iso);

CREATE INDEX IF NOT EXISTS idx_article_publish_at ON article (publish_at);
CREATE INDEX IF NOT EXISTS idx_article_paper_uuid ON article (paper_uuid);
CREATE INDEX IF NOT EXISTS idx_crawl_paper_uuid ON crawl (paper_uuid);
CREATE UNIQUE INDEX IF NOT EXISTS uq_category_set_paper_url ON category_set (paper_uuid, url);
CREATE INDEX IF NOT EXISTS idx_article_country_ref_source ON article_country_reference (source_country_iso);
CREATE INDEX IF NOT EXISTS idx_article_country_ref_target ON article_country_reference (target_country_iso);


