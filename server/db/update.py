import uuid
import json

from server.db.db import conn
from psycopg2.extras import DictCursor


def update():
    with open('server/db/newspaper_store.json', 'r') as f:
        papers_json = json.load(f)

    with conn.cursor(cursor_factory=DictCursor) as c:
        c.execute('''
            SELECT p.uuid, p.url, cs.url FROM paper p
            JOIN category_set cs on cs.paper_uuid = p.uuid 
        ''')

        db_results = c.fetchall()

        db_results_formatted = {}
        for db_result in db_results:
            paper_uuid, url, category_url = db_result
            if url not in db_results_formatted:
                db_results_formatted[url] = {"uuid": '', "category_urls": []}

            db_results_formatted[url]['uuid'] = paper_uuid
            db_results_formatted[url]['category_urls'].append(category_url)

        for paper_json in papers_json:
            url = paper_json['url']

            # Add paper if doesn't exist
            if url not in db_results_formatted:
                print('Adding paper', url)
                uuid_paper = str(uuid.uuid4())

                c.execute("""
                    INSERT INTO paper VALUES (%s, %s, %s, %s)""", (
                        uuid_paper,
                        paper_json['url'],
                        paper_json['country'],
                        paper_json['lang']
                    )
                )

                for category_url in paper_json['category_urls']:
                    print('Adding categories', category_url)
                    c.execute('''INSERT INTO category_set VALUES (%s, %s)''', (uuid_paper, category_url))

            else:
                # check if categories are in DB
                uuid_paper = db_results_formatted[url]
                for category_url in paper_json['category_urls']:
                    if category_url not in db_results_formatted[url]['category_urls']:
                        print('Adding categories {} to {}'.format(category_url, url))
                        c.execute('''INSERT INTO category_set VALUES (%s, %s)''', (uuid_paper, category_url))

                print('Finished update to', url)

    conn.commit()

if __name__ == '__main__':
    update()
