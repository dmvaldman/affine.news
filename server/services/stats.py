import datetime

from server.db.db import conn
from psycopg2.extras import DictCursor


def occurences_over_time(query, date_start, date_end, country=None):
    command = '''
        SELECT 
          date,
          iso,
          total,
          CAST(
            avg(total) 
                OVER (
                    PARTITION BY iso
                    ORDER BY date ROWS BETWEEN 3 PRECEDING AND 3 FOLLOWING
                ) 
            as FLOAT) as rolling
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

    obj = {}  # type sig: {iso: {date, iso, total, rolling}}
    for result in results:
        iso = result['iso']

        if iso not in obj:
            obj[iso] = []

        datum = {}
        for key in result.keys():
            datum[key] = result[key]

        obj[iso].append(datum)
    return obj


if __name__ == '__main__':
    query_str = 'Trump'
    today = datetime.date.today()
    date_start = today - datetime.timedelta(days=7)
    date_end = today - datetime.timedelta(days=0)

    params = {
        'query': query_str,
        'date_start': str(date_start),
        'date_end': str(date_end)
    }
    query_result = occurences_over_time(query_str, date_start, date_end)
    print(query_result)
