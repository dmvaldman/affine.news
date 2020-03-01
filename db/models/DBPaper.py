import sqlite3
import uuid
from Paper import Paper
import os

path = os.path.dirname(os.path.abspath(__file__))
db = os.path.join(path, '../paper.db')

conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
c = conn.cursor()


def get_papers_from_rows(results):
    if not results:
        return []

    papers = []

    category_urls = []
    prev_result = None

    for result in results:
        if prev_result is not None and prev_result['uuid'] != result['uuid']:
            paper = Paper(
                url=prev_result['url'],
                lang=prev_result['lang'],
                country=prev_result['country'],
                uuid=prev_result['uuid'],
                category_urls=category_urls)

            papers.append(paper)
            category_urls = []

        prev_result = result
        category_urls.append(result['category_url'])

    if len(category_urls) > 0:
        paper = Paper(
            url=result['url'],
            lang=result['lang'],
            country=result['country'],
            uuid=result['uuid'],
            category_urls=category_urls)
        papers.append(paper)

    return papers


class DBPaper:
    @staticmethod
    def get_all():
        with conn:
            c.execute('''
                SELECT p.uuid, p.country, p.lang, p.url, cs.url as category_url FROM paper p
                JOIN category_set cs on cs.paper_uuid = p.uuid
            ''')
            return get_papers_from_rows(c.fetchall())

    @staticmethod
    def get_paper_by_url(url):
        with conn:
            c.execute('''
                SELECT p.uuid, p.country, p.lang, p.url as url, cs.url as category_url FROM paper p                 
                JOIN category_set cs on cs.paper_uuid = p.uuid
                WHERE p.url=:url 
                ''', {"url": url})
            return get_papers_from_rows(c.fetchall())

    @staticmethod
    def create(paper):
        paper_uuid = uuid.uuid4()
        with conn:
            c.execute("""INSERT INTO paper VALUES (
                :uuid 
                :url, 
                :country,
                :lang                                 
            )""", {
                "uuid": str(paper_uuid),
                "url": paper.url,
                "country": paper.country,
                "lang": paper.lang
            })

            for category_url in paper.category_urls:
                c.execute('''INSERT INTO category_set VALUES (?, ?)''', (str(paper_uuid), category_url))

            conn.commit()

    @staticmethod
    def create_many(papers):
        for paper in papers:
            DBPaper.create(paper)

    @staticmethod
    def update(paper, **kwargs):
        pass

    @staticmethod
    def delete(paper):
        pass


if __name__ == '__main__':
    results = DBPaper.get_all()
    print(results)
#
#     results = DBPaper.get_paper_by_url('http://www.hurriyet.com.tr/')
#     print(results)
