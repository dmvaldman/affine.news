import sqlite3
import uuid
import json

conn = sqlite3.connect('paper.db')
c = conn.cursor()

c.execute('''DROP TABLE IF EXISTS category_set''')
c.execute('''DROP TABLE IF EXISTS paper''')
c.execute('''DROP TABLE IF EXISTS crawl''')
c.execute('''DROP TABLE IF EXISTS article''')

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
        start_at TEXT,
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
        publish_at TEXT,
        text_translated TEXT,
        keywords_translated TEXT,
        paper_uuid TEXT,
        crawl_uuid TEXT,        
        FOREIGN KEY(paper_uuid) REFERENCES paper(uuid)
        FOREIGN KEY(crawl_uuid) REFERENCES crawl(uuid)
    )
""")

with open('newspaper_store.json', 'r') as f:
    papers_json = json.load(f)

for paper_json in papers_json:
    if 'uuid' not in paper_json:
        uuid_paper = str(uuid.uuid4())
    else:
        uuid_paper = paper_json['uuid']

    category_set_uuid = str(uuid.uuid4())

    c.execute("""
            INSERT INTO paper VALUES (
                :uuid, 
                :url, 
                :country,
                :lang
            )
        """, {
            "uuid": uuid_paper,
            "url": paper_json['url'],
            "country": paper_json['country'],
            "lang": paper_json['lang']
        }
    )

    for url in paper_json['category_urls']:
        c.execute('''INSERT INTO category_set VALUES (?, ?)''', (uuid_paper, url))

conn.commit()

conn.close()
