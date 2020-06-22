from server.db.db import conn
from psycopg2.extras import DictCursor

class DBArticle:
    @staticmethod
    def get_article_by_url(url):
        pass

    @staticmethod
    def create(article):
        with conn.cursor(cursor_factory=DictCursor) as c:
            try:
                c.execute("""
                    INSERT INTO article (                
                        url, 
                        img_url,
                        title,
                        title_translated,
                        lang,          
                        text,
                        publish_at,
                        text_translated,
                        paper_uuid,
                        crawl_uuid
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """, (
                        article.url,
                        article.img_url,
                        article.title,
                        article.title_translated,
                        article.lang,
                        article.text.lower(),
                        article.publish_at.isoformat(),
                        article.text_translated,
                        str(article.paper_uuid),
                        str(article.crawl_uuid)
                    )
                )
            except Exception as e:
                print(e)
        conn.commit()

    @staticmethod
    def update(article, **kwargs):
        pass

    @staticmethod
    def delete(article):
        pass

    @staticmethod
    def cache_hit(article):
        query = '''SELECT * FROM article WHERE url=%s'''
        data = (article.url,)
        with conn.cursor(cursor_factory=DictCursor) as c:
            c.execute(query, data)
            return c.fetchone()
