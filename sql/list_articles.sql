SELECT crawl.created_at, p.country, a.url, a.title_translated, a.title FROM crawl
JOIN paper p on p.uuid = crawl.paper_uuid
JOIN article a on a.crawl_uuid = crawl.uuid
ORDER BY created_at desc, p.country
LIMIT 100