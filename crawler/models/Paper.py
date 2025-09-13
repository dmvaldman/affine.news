class Papers:
    def __init__(self):
        self.papers = []

    def __len__(self):
        return len(self.papers)

    def __str__(self):
        return str(self.papers)

    def __iter__(self):
        self._index = 0
        return self

    def __next__(self):
        if self._index < len(self.papers):
            result = self.papers[self._index]
            self._index += 1
            return result
        else:
            raise StopIteration

    def add(self, paper):
        self.papers.append(paper)

    def to_json(self):
        return [paper.to_json() for paper in self.papers]

    def from_json(self, data):
        for datum in data:
            paper = Paper(**datum)
            self.add(paper)

    def load(self):
        from crawler.db.models.DBPaper import DBPaper
        self.papers = DBPaper.get_all()
        return self

    def save(self):
        from crawler.db.models.DBPaper import DBPaper
        for paper in self.papers:
            DBPaper.save(paper)


class Paper(object):
    def __init__(self, url, country=None, iso=None, lang=None, category_urls=None, whitelist=None, uuid=None):
        if (url is None) or ('http' not in url):
            raise Exception('Url is required and must be valid')

        self.url = url
        self.country = country
        self.iso = iso
        self.lang = lang
        self.category_urls = category_urls or []
        self.whitelist = whitelist or []
        self.uuid = uuid
        self.articles = []

    def __repr__(self):
        return 'Newspaper {0} from {1} in `{2}` language.'.format(self.url, self.country, self.lang)

    def set_uuid(self, paper_uuid):
        self.uuid = paper_uuid

    def to_json(self):
        return {
            "uuid": str(self.uuid),
            "country": self.country,
            "iso": self.iso,
            "lang": self.lang,
            "url": self.url,
            "category_urls": self.category_urls
        }

    def save(self):
        from crawler.db.models.DBPaper import DBPaper
        DBPaper.save(self)

    @staticmethod
    def load_from_url(url):
        from crawler.db.models.DBPaper import DBPaper
        return DBPaper.get_paper_by_url(url)

    @staticmethod
    def load_from_uuid(uuid):
        from crawler.db.models.DBPaper import DBPaper
        return DBPaper.get_paper_by_uuid(uuid)
