import re
from server.db.db import conn
from psycopg2.extras import DictCursor


def run(query, date_start, date_end, country=None):
    command = '''SELECT p.country as country, p.ISO as iso, p.url as paper_url, p.lang, a.url as article_url, a.publish_at, a.title_translated FROM article a
        JOIN paper p on p.uuid = a.paper_uuid
        WHERE a.publish_at >= %s
        AND DATE(a.publish_at) <= %s
        AND a.title_translated is not NULL
        ORDER BY a.publish_at desc'''

    params = (str(date_start), str(date_end))

    if country is not None:
        command += ' AND p.country = %s'
        params += (country, )

    with conn.cursor(cursor_factory=DictCursor) as c:
        c.execute(command, params)
        results = c.fetchall()

    results_matched = []
    for result in results:
        title = result['title_translated']

        print(re.search(query, title, re.IGNORECASE), query, title)
        for word in query.split(','):
            if re.search(word, title, re.IGNORECASE):
                results_matched.append(result)

    by_country = {}
    for result_matched in results_matched:
        iso = result_matched["iso"]
        if iso not in by_country:
            by_country[iso] = []
        by_country[iso].append({
            "article_url": result_matched['article_url'],
            "title": result_matched['title_translated'],
            "paper_url": result_matched['paper_url'],
            "publish_at": result_matched['publish_at'],
            "lang": result_matched['lang']
        })

    for country, articles in by_country.items():
        print('\n')
        print(country)
        print('\n')
        for article in articles:
            print(article['title'], article['article_url'])

    return by_country
