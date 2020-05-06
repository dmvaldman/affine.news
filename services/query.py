import re
import sqlite3
import os

path = os.path.dirname(os.path.abspath(__file__))
db = os.path.join(path, '../db/paper.db')

conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
c = conn.cursor()

def run(query, date_start, date_end, country=None):
    command = '''SELECT p.country as country, p.url as paper_url, a.url as article_url, a.keywords_translated, a.title_translated, a.text_translated FROM article a
        JOIN paper p on p.uuid = a.paper_uuid
        WHERE a.publish_at >= :date_start
        AND a.publish_at <= :date_end'''

    params = {
        "date_start": date_start,
        "date_end": date_end
    }

    if country:
        command += ' AND p.country = country'
        params["country"] = country

    c.execute(command, params)

    results = c.fetchall()

    results_matched = []
    for result in results:
        keywords = result['keywords_translated']
        title = result['title_translated']

        if keywords is None and title is None:
            continue

        if re.search(query, keywords, re.IGNORECASE) or re.search(query, title, re.IGNORECASE):
            results_matched.append(result)

    by_country = {}
    for result_matched in results_matched:
        country = result_matched["country"]
        if country not in by_country:
            by_country[country] = []
        by_country[country].append({
            "article_url": result_matched['article_url'],
            "title": result_matched['title_translated'],
            "paper_url": result_matched['paper_url']
        })

    for country, articles in by_country.items():
        print('\n')
        print(country)
        print('\n')
        for article in articles:
            print(article['title'], article['article_url'])
