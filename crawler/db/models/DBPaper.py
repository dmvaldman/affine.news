from crawler.models.Paper import Paper
from crawler.db.db import conn
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
                iso=prev_result['iso'],
                uuid=prev_result['uuid'],
                whitelist=prev_result['whitelist'],
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
            iso=result['iso'],
            uuid=result['uuid'],
            whitelist=result['whitelist'],
            category_urls=category_urls)
        papers.append(paper)

    return papers


class DBPaper:
    def __init__(self, uuid, url, country, iso, lang, category_urls=None, whitelist=None):
        self.uuid = uuid
        self.url = url
        self.country = country
        self.iso = iso
        self.lang = lang
        self.category_urls = category_urls or []
        self.whitelist = whitelist or []

    def __repr__(self):
        return f"DBPaper(uuid={self.uuid}, url={self.url}, country={self.country}, iso={self.iso}, lang={self.lang}, category_urls={self.category_urls}, whitelist={self.whitelist})"

    @staticmethod
    def get_all():
        with conn.cursor(cursor_factory=DictCursor) as c:
            c.execute('''
                SELECT p.uuid, p.country, p.iso, p.lang, p.url, p.whitelist, cs.url as category_url FROM paper p
                JOIN category_set cs on cs.paper_uuid = p.uuid
            ''')
            return get_papers_from_rows(c.fetchall())

    @staticmethod
    def get_paper_by_url(url):
        with conn.cursor(cursor_factory=DictCursor) as c:
            c.execute('''
                SELECT p.uuid, p.country, p.iso, p.lang, p.url as url, p.whitelist, cs.url as category_url FROM paper p
                JOIN category_set cs on cs.paper_uuid = p.uuid
                WHERE p.url=%s
                ''', (url,))
            return get_papers_from_rows(c.fetchall())[0]

    @staticmethod
    def get_paper_by_uuid(uuid):
        with conn.cursor(cursor_factory=DictCursor) as c:
            c.execute('''
                    SELECT p.uuid, p.country, p.iso, p.lang, p.url as url, p.whitelist, cs.url as category_url FROM paper p
                    JOIN category_set cs on cs.paper_uuid = p.uuid
                    WHERE p.uuid=%s
                    ''', (uuid,))
            return get_papers_from_rows(c.fetchall())[0]

    def save(self):
        """
        Saves the current state of the paper object back to the database.
        This method performs an "upsert" (insert or update).
        """
        with conn.cursor() as cur:
            # First, upsert the core paper details
            cur.execute(
                """
                INSERT INTO paper (uuid, url, country, iso, lang, whitelist)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (uuid) DO UPDATE SET
                    url = EXCLUDED.url,
                    country = EXCLUDED.country,
                    iso = EXCLUDED.iso,
                    lang = EXCLUDED.lang,
                    whitelist = EXCLUDED.whitelist;
                """,
                (self.uuid, self.url, self.country, self.iso, self.lang, self.whitelist)
            )

            # Second, manage category_urls
            # Delete categories that are no longer in the list for this paper
            tuple_list = tuple(self.category_urls) or ('',)
            cur.execute("DELETE FROM category_set WHERE paper_uuid = %s AND url NOT IN %s", (self.uuid, tuple_list))

            # Insert new categories, ignoring ones that already exist
            if self.category_urls:
                for url in self.category_urls:
                    cur.execute(
                        """
                        INSERT INTO category_set (paper_uuid, url)
                        VALUES (%s, %s)
                        ON CONFLICT (paper_uuid, url) DO NOTHING
                        """,
                        (self.uuid, url)
                    )

    @staticmethod
    def update(paper, **kwargs):
        pass

    @staticmethod
    def delete(paper):
        pass


if __name__ == '__main__':
    results = DBPaper.get_all()
    print(results)
