SELECT p.country as country, p.url as paper_url, a.url as article_url, a.publish_at, a.title_translated FROM article a
JOIN paper p on p.uuid = a.paper_uuid
WHERE lower(a.title_translated) LIKE '%trump%'
ORDER BY DATE(a.publish_at) desc, country asc
LIMIT 50