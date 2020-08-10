from server.db.db import conn
from psycopg2.extras import DictCursor
from datetime import date

def delete(date):
    with conn.cursor(cursor_factory=DictCursor) as c:
        c.execute('''
            DELETE FROM article a
            USING crawl c
            WHERE c.uuid = a.crawl_uuid
            AND DATE(c.start_at) = DATE(%s) 
        ''', (date,))

        c.execute('''
            DELETE FROM crawl c
            WHERE DATE(c.start_at) = DATE(%s)
        ''', (date,))

    conn.commit()

if __name__ == '__main__':
    date = date.today()
    delete(date)
