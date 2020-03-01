import sqlite3
import os
from Crawler import CrawlStatus

path = os.path.dirname(os.path.abspath(__file__))
db = os.path.join(path, '../paper.db')

conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
c = conn.cursor()


class DBCrawl:
    @staticmethod
    def create(crawl):
        with conn:
            c.execute("""INSERT INTO crawl VALUES ( 
                        :uuid,
                        :start_at,                                                 
                        :status,
                        :max_articles,
                        :paper_uuid                        
                    )""", {
                "uuid": str(crawl.uuid),
                "max_articles": crawl.max_articles,
                "start_at": crawl.start_at.isoformat(),
                "status": crawl.status.value,
                "paper_uuid": str(crawl.paper_uuid)
            })
            conn.commit()
        return True

    @staticmethod
    def cache_hit(crawl):
        with conn:
            c.execute('''
                SELECT * FROM crawl 
                WHERE paper_uuid=:paper_uuid
                AND status=:complete_status
                AND start_at >=:start_at
                AND max_articles=:max_articles           
            ''', {
                "paper_uuid": str(crawl.paper_uuid),
                "complete_status": CrawlStatus.COMPLETED.value,
                "start_at": crawl.start_at.isoformat(),
                "max_articles": crawl.max_articles
            })

        return c.fetchone()

    @staticmethod
    def update_status(crawl, status):
        with conn:
            c.execute(('''
                UPDATE crawl SET status=:status
                WHERE uuid=:uuid
            '''), {"status": status.value, "uuid": str(crawl.uuid)})
            conn.commit()
        return True

    @staticmethod
    def delete(crawl):
        pass
