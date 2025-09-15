from crawler.db.db import conn
from psycopg2.extras import DictCursor

class DBArticle:
    @staticmethod
    def get_article_by_url(url):
        pass

    @staticmethod
    def save(article):
        with conn.cursor(cursor_factory=DictCursor) as c:
            try:
                c.execute("""
                    INSERT INTO article (
                        url,
                        img_url,
                        title,
                        title_translated,
                        lang,
                        publish_at,
                        title_embedding,
                        paper_uuid,
                        crawl_uuid
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (url) DO UPDATE SET
                        url=EXCLUDED.url,
                        img_url=EXCLUDED.img_url,
                        title=EXCLUDED.title,
                        title_translated=EXCLUDED.title_translated,
                        lang=EXCLUDED.lang,
                        publish_at=EXCLUDED.publish_at,
                        title_embedding=EXCLUDED.title_embedding,
                        paper_uuid=EXCLUDED.paper_uuid,
                        crawl_uuid=EXCLUDED.crawl_uuid
                    """, (
                        article.url,
                        article.img_url,
                        article.title,
                        article.title_translated,
                        article.lang,
                        article.publish_at.isoformat(),
                        article.title_embedding,
                        str(article.paper_uuid),
                        article.crawl_uuid,
                    )
                )
            except Exception as e:
                print(e)
        conn.commit()

    @staticmethod
    def cache_hit(article):
        query = '''SELECT * FROM article WHERE url=%s and title is not null'''
        data = (article.url, )
        with conn.cursor(cursor_factory=DictCursor) as c:
            c.execute(query, data)
            return c.fetchone()
