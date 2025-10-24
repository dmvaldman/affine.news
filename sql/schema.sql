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

CREATE TABLE IF NOT EXISTS topic_spectrum_cache (
    id SERIAL PRIMARY KEY,
    topic TEXT NOT NULL,
    spectrum_name TEXT,
    spectrum_description TEXT,
    spectrum_points JSONB,
    articles_by_country JSONB,
    topic_date DATE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(topic, topic_date)
);

CREATE INDEX IF NOT EXISTS idx_article_publish_at ON article (publish_at);
CREATE INDEX IF NOT EXISTS idx_article_paper_uuid ON article (paper_uuid);
CREATE INDEX IF NOT EXISTS idx_crawl_paper_uuid ON crawl (paper_uuid);
CREATE UNIQUE INDEX IF NOT EXISTS uq_category_set_paper_url ON category_set (paper_uuid, url);

-- Indexes for the matrix building query
CREATE INDEX IF NOT EXISTS idx_article_publish_at_translated ON article (publish_at)
WHERE title_translated IS NOT NULL AND title_translated != '';
CREATE INDEX IF NOT EXISTS idx_article_embedding ON article (title_embedding)
WHERE title_embedding IS NOT NULL;

-- Indexes for topic spectrum cache
CREATE INDEX IF NOT EXISTS idx_topic_spectrum_cache_topic ON topic_spectrum_cache (topic);
CREATE INDEX IF NOT EXISTS idx_topic_spectrum_cache_date ON topic_spectrum_cache (topic_date);


