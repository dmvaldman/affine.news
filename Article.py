from datetime import date


class Articles:
    def __init__(self):
        pass


class Article:
    def __init__(self, url='', keywords='', text='', img_url='', title='', publish_at=None, lang='',
                 paper_uuid=None, crawl_uuid=None):
        self.url = url
        self.img_url = img_url
        self.title = title
        self.keywords = keywords
        self.text = text
        self.lang = lang
        self.publish_at = publish_at or date.today()
        self.paper_uuid = paper_uuid
        self.crawl_uuid = crawl_uuid

        self.title_translated = None
        self.keywords_translated = None
        self.text_translated = None

    def load(self):
        pass

    def cache_hit(self):
        from db.models.DBArticle import DBArticle
        return DBArticle.cache_hit(self)

    def save(self):
        from db.models.DBArticle import DBArticle
        DBArticle.create(self)
