from crawler.db.db import conn
from psycopg.rows import dict_row


class DBCrawl:
    @staticmethod
    def create(crawl):
        with conn.cursor(row_factory=dict_row) as c:
            c.execute("""
                INSERT INTO crawl (
                    uuid,
                    created_at,
                    status,
                    max_articles,
                    paper_uuid
                ) VALUES (%s, %s, %s, %s, %s)""", (
                    str(crawl.uuid),
                    crawl.created_at.isoformat(),
                    crawl.status.value,
                    crawl.max_articles,
                    str(crawl.paper_uuid)
                )
            )

        conn.commit()
        return True

    @staticmethod
    def update_status(crawl, status):
        with conn.cursor(row_factory=dict_row) as c:
            c.execute('''
                UPDATE crawl SET status=%s
                WHERE uuid=%s
            ''', (
                status.value,
                str(crawl.uuid)
            ))
        conn.commit()
        return True

    @staticmethod
    def delete(crawl):
        pass

    @staticmethod
    def close():
        conn.close()
