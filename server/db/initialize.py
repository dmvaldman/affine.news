import uuid
import json
from server.db.db import conn
from psycopg2.extras import DictCursor


def init():
    with conn.cursor(cursor_factory=DictCursor) as c:
        c.execute('''DROP TABLE IF EXISTS category_set cascade''')
        c.execute('''DROP TABLE IF EXISTS paper cascade''')
        c.execute('''DROP TABLE IF EXISTS crawl cascade''')
        c.execute('''DROP TABLE IF EXISTS article cascade''')

        c.execute("""
            CREATE TABLE paper (
                uuid TEXT PRIMARY KEY,
                url TEXT, 
                country TEXT, 
                lang TEXT
            )
        """)

        c.execute("""
            CREATE TABLE category_set (
                paper_uuid TEXT, 
                url TEXT,
                FOREIGN KEY(paper_uuid) REFERENCES paper(uuid)
            )
        """)

        c.execute("""
            CREATE TABLE crawl (
                uuid TEXT PRIMARY KEY,
                start_at TIMESTAMP,
                status INTEGER,
                max_articles INTEGER,
                paper_uuid TEXT,        
                FOREIGN KEY(paper_uuid) REFERENCES paper(uuid)
            )
        """)

        c.execute("""
            CREATE TABLE article (
                url TEXT PRIMARY KEY,        
                img_url TEXT,
                title TEXT,
                title_translated TEXT,
                lang TEXT,        
                keywords TEXT,        
                text TEXT,
                publish_at TIMESTAMP,
                text_translated TEXT,
                keywords_translated TEXT,
                paper_uuid TEXT,
                crawl_uuid TEXT,        
                FOREIGN KEY(paper_uuid) REFERENCES paper(uuid),
                FOREIGN KEY(crawl_uuid) REFERENCES crawl(uuid)
            )
        """)

        print('opening')
        with open('./server/db/newspaper_store.json', 'r') as f:
            papers_json = json.load(f)

        print('done')

        for paper_json in papers_json:
            uuid_paper = str(uuid.uuid4())

            c.execute(
                """INSERT INTO paper (uuid, url, country, lang) VALUES (%s, %s, %s, %s)""",
                (uuid_paper, paper_json['url'], paper_json['country'], paper_json['lang'])
            )

            print('inserted', (uuid_paper, paper_json['url'], paper_json['country'], paper_json['lang']))

            for url in paper_json['category_urls']:
                c.execute('''INSERT INTO category_set (paper_uuid, url) VALUES (%s, %s)''', (uuid_paper, url))

    conn.commit()


