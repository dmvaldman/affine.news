import uuid
from server.models.Paper import Paper
from server.db.db import conn
from psycopg2.extras import DictCursor


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
        with conn.cursor(cursor_factory=DictCursor) as c:
            c.execute('''
                SELECT p.uuid, p.country, p.lang, p.url, cs.url as category_url FROM paper p
                JOIN category_set cs on cs.paper_uuid = p.uuid
            ''')
            return get_papers_from_rows(c.fetchall())

    @staticmethod
    def get_paper_by_url(url):
        with conn.cursor(cursor_factory=DictCursor) as c:
            c.execute('''
                SELECT p.uuid, p.country, p.lang, p.url as url, cs.url as category_url FROM paper p                 
                JOIN category_set cs on cs.paper_uuid = p.uuid
                WHERE p.url=%s
                ''', (url,))
            return get_papers_from_rows(c.fetchall())

    @staticmethod
    def create(paper):
        paper_uuid = uuid.uuid4()
        with conn.cursor(cursor_factory=DictCursor) as c:
            c.execute("""INSERT INTO paper (
                uuid 
                url, 
                country,
                lang) VALUES (%s, %s, %s, %s)""", (
                    str(paper_uuid),
                    paper.url,
                    paper.country,
                    paper.lang
                )
            )

            for category_url in paper.category_urls:
                c.execute('''INSERT INTO category_set VALUES (%s, %s)''', (str(paper_uuid), category_url))

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
