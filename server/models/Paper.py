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
        from server.db.models.DBPaper import DBPaper
        self.papers = DBPaper.get_all()

    def save(self):
        from server.db.models.DBPaper import DBPaper
        DBPaper.create_many(self.papers)


class Paper:
    def __init__(self, url='', lang='', country='', uuid='', category_urls=None):
        self.url = url
        self.lang = lang
        self.country = country
        self.uuid = uuid
        self.category_urls = category_urls

    def __repr__(self):
        return 'Newspaper {0} from {1} in {2} language. Categories {3}'.format(self.url, self.country,
                                                                           self.lang,
                                                                           self.category_urls)

    def set_uuid(self, paper_uuid):
        self.uuid = paper_uuid

    def to_json(self):
        return {
            "uuid": str(self.uuid),
            "country": self.country,
            "lang": self.lang,
            "url": self.url,
            "category_urls": self.category_urls
        }

    def save(self):
        from server.db.models.DBPaper import DBPaper
        DBPaper.create(self)

    @staticmethod
    def load_from_url(url):
        from server.db.models.DBPaper import DBPaper
        return DBPaper.get_paper_by_url(url)

    @staticmethod
    def load_from_uuid(uuid):
        from server.db.models.DBPaper import DBPaper
        return DBPaper.get_paper_by_uuid(uuid)