from server.db.db import conn
from psycopg2.extras import DictCursor


def occurences_over_time(query, date_start, date_end, country=None):
    command = '''
        SELECT 
          date,
          iso,
          total,
          avg(total) OVER (
            PARTITION BY iso
            ORDER BY date ROWS BETWEEN 3 PRECEDING AND 3 FOLLOWING
          ) as rolling
        FROM (
          SELECT 
            DATE(a.publish_at) as date,
            p.iso as iso,
            count(*) as total
          FROM article a
          JOIN paper p on a.paper_uuid = p.uuid
          WHERE DATE(a.publish_at) >= DATE(%s)
          AND DATE(a.publish_at) <= DATE(%s)
          AND LOWER(a.title) LIKE %s
          GROUP BY 1, 2          
        ) foo    
        ORDER BY 1
    '''

    params = (str(date_start), str(date_end), '%' + query.lower() + '%')

    with conn.cursor(cursor_factory=DictCursor) as c:
        c.execute(command, params)
        results = c.fetchall()

    return results
