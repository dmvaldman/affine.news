import uuid
import nltk
from enum import Enum
from datetime import date
from server.lib.newspaper import newspaper
from server.models.Article import Article


nltk.download('punkt')


class CrawlStatus(Enum):
    STARTED = 1
    COMPLETED = 2


class Crawler:
    def __init__(self, max_articles=None):
        self.max_articles = max_articles

    def crawl_papers(self, papers, verbose=True):
        for paper in papers:
            self.crawl_paper(paper, verbose=verbose)

    def crawl_paper(self, paper, verbose=True):
        if verbose:
            print('Building paper for', paper)

        todays_date = date.today()

        crawl = Crawl(
            start_at=todays_date,
            max_articles=self.max_articles,
            status=CrawlStatus.STARTED,
            paper_uuid=paper.uuid)

        if crawl.cache_hit():
            if verbose:
                print('crawl cache hit', crawl)
            crawl.update_status(CrawlStatus.COMPLETED)
            return crawl

        crawl.save()

        paper_build = newspaper.build(
            paper.url,
            language=paper.lang,
            memoize_articles=False,
            fetch_images=False,
            request_timeout=20,
            max_articles=self.max_articles,
            category_urls=paper.category_urls)

        articles_index = 0
        count_failure = 0
        count_success = 0

        for paper_article in paper_build.articles:
            articles_index += 1

            try:
                self.crawl_article(paper_article)
                count_success += 1
            except Exception as err:
                count_failure += 1
                if verbose:
                    print(err)
                continue

            if not paper_article.text:
                text = paper_article.meta_description
            else:
                text = paper_article.text

            if not text:
                continue

            img_url = paper_article.meta_img or paper_article.top_img or ''

            article = Article(
                url=paper_article.url,
                title=paper_article.title,
                img_url=img_url,
                text=text,
                publish_at=paper_article.publish_date or todays_date,
                lang=paper.lang,
                paper_uuid=paper.uuid,
                crawl_uuid=crawl.uuid
            )

            if article.cache_hit():
                if verbose:
                    print('Article cache hit', article)
                continue

            article.save()

        crawl.update_status(CrawlStatus.COMPLETED)

        if len(paper_build.articles) > 0:
            if verbose:
                success_rate = 100 * count_success / (count_failure + count_success)
                print('Success: {}, Failure: {}, Rate: {}%:'.format(count_success, count_failure, success_rate))
        else:
            if verbose:
                print('Crawl failure for ', paper)

        return crawl

    def crawl_article(self, article, verbose=True):
        if verbose:
            print('Downloading article', article)

        article.download()

        if article.download_state == 1:
            raise Exception('Download Failed for {}'.format(article))

        article.parse()
        article.nlp()

        return article


class Crawl:
    def __init__(self, start_at=None, max_articles=0, status=None, paper_uuid=None):
        self.uuid = uuid.uuid4()
        self.max_articles = max_articles
        self.start_at = start_at
        self.status = status
        self.paper_uuid = paper_uuid

    def __str__(self):
        return 'Crawl of {}. Started at {}. Status {}'.format(self.paper_uuid, self.start_at, self.status)

    def cache_hit(self):
        from server.db.models.DBCrawl import DBCrawl
        return DBCrawl.cache_hit(self)

    def update_status(self, status):
        from server.db.models.DBCrawl import DBCrawl
        self.status = status
        DBCrawl.update_status(self, status)
        return True

    def load(self):
        pass

    def save(self):
        from server.db.models.DBCrawl import DBCrawl
        return DBCrawl.create(self)

    def close(self):
        from server.db.models.DBCrawl import DBCrawl
        return DBCrawl.close()
