import sqlite3
import os

path = os.path.dirname(os.path.abspath(__file__))
db = os.path.join(path, '../paper.db')

conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
c = conn.cursor()


class DBArticle:
    @staticmethod
    def get_article_by_url(url):
        pass

    @staticmethod
    def create(article):
        with conn:
            c.execute("""INSERT INTO article VALUES ( 
                :url, 
                :img_url,
                :title,
                :title_translated,
                :lang,
                :keywords,                 
                :text,
                :publish_at,
                :text_translated,
                :keywords_translated,
                :paper_uuid,
                :crawl_uuid
            )""", {
                "url": article.url,
                "img_url": article.img_url,
                "title": article.title,
                "title_translated": article.title_translated,
                "lang": article.lang,
                "keywords": ', '.join(article.keywords).lower(),
                "text": article.text.lower(),
                "publish_at": article.publish_at.isoformat(),
                "text_translated": article.text_translated,
                "keywords_translated": article.keywords_translated,
                "paper_uuid": str(article.paper_uuid),
                "crawl_uuid": str(article.crawl_uuid)
            })
            conn.commit()

    @staticmethod
    def update(article, **kwargs):
        pass

    @staticmethod
    def delete(article):
        pass

    @staticmethod
    def cache_hit(article):
        with conn:
            c.execute('''
                SELECT * FROM article WHERE url=:url              
            ''', {"url": article.url})
        return c.fetchone()
