-- Neon schema for Affine News

CREATE TABLE IF NOT EXISTS paper (
    uuid TEXT PRIMARY KEY,
    url TEXT,
    country TEXT,
    ISO TEXT,
    lang TEXT
);

CREATE TABLE IF NOT EXISTS category_set (
    paper_uuid TEXT,
    url TEXT,
    FOREIGN KEY(paper_uuid) REFERENCES paper(uuid)
);

CREATE TABLE IF NOT EXISTS crawl (
    uuid TEXT PRIMARY KEY,
    start_at TIMESTAMP,
    status INTEGER,
    max_articles INTEGER,
    paper_uuid TEXT,
    FOREIGN KEY(paper_uuid) REFERENCES paper(uuid)
);

CREATE TABLE IF NOT EXISTS article (
    url TEXT PRIMARY KEY,
    img_url TEXT,
    title TEXT,
    title_translated TEXT,
    lang TEXT,
    keywords TEXT,
    text TEXT,
    publish_at TIMESTAMP,
    text_translated TEXT,
    keywords_translated TEXT,
    paper_uuid TEXT,
    crawl_uuid TEXT,
    FOREIGN KEY(paper_uuid) REFERENCES paper(uuid),
    FOREIGN KEY(crawl_uuid) REFERENCES crawl(uuid)
);

CREATE INDEX IF NOT EXISTS idx_article_publish_at ON article (publish_at);
CREATE INDEX IF NOT EXISTS idx_article_paper_uuid ON article (paper_uuid);
CREATE INDEX IF NOT EXISTS idx_crawl_paper_uuid ON crawl (paper_uuid);
CREATE UNIQUE INDEX IF NOT EXISTS uq_category_set_paper_url ON category_set (paper_uuid, url);


