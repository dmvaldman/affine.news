import uuid
from enum import Enum
from datetime import date
import newspaper
from crawler.models.Article import Article


class CrawlStatus(Enum):
    STARTED = 1
    COMPLETED = 2


class Crawler:
    def __init__(self, max_articles=None):
        self.max_articles = max_articles

    def crawl_papers(self, papers, verbose=True):
        for paper in papers:
            self.crawl_paper(paper, verbose=verbose)

    def crawl_paper(self, paper, verbose=True, ignore_cache=False):
        if verbose:
            print('Building', paper)

        todays_date = date.today()

        crawl = Crawl(
            created_at=todays_date,
            max_articles=self.max_articles,
            status=CrawlStatus.STARTED,
            paper_uuid=paper.uuid)

        if ignore_cache and crawl.cache_hit():
            crawl.update_status(CrawlStatus.COMPLETED)
            if verbose:
                print('Cache hit', crawl)
            return crawl

        crawl.save()

        try:
            paper_build = newspaper.build(
                paper.url,
                language=paper.lang,
                memoize_articles=False,
                fetch_images=False,
                request_timeout=20,
                min_word_count=100,
                category_urls=paper.category_urls)
        except Exception as e:
            print(f"Error crawling {paper.url}: {e}", e)
            return None

        articles_index = 0
        count_failure = 0
        count_success = 0

        for paper_article in paper_build.articles:
            articles_index += 1

            if self.max_articles is not None and count_success > self.max_articles:
                break

            try:
                self.crawl_article(paper_article)
                count_success += 1
            except Exception as err:
                count_failure += 1
                if verbose:
                    print(err)
                continue

            img_url = paper_article.meta_img or paper_article.top_img or ''

            article = Article(
                url=paper_article.url,
                title=paper_article.title,
                img_url=img_url,
                publish_at=paper_article.publish_date or todays_date,
                lang=paper.lang,
                paper_uuid=paper.uuid,
                crawl_uuid=crawl.uuid
            )

            if ignore_cache and article.cache_hit():
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

        crawl.stats['downloaded'] = count_success
        crawl.stats['failed'] = count_failure

        return crawl

    def crawl_article(self, article, verbose=True):
        if verbose:
            print('Downloading article', article.url)

        article.download()

        if article.download_state == 1:
            raise Exception('Download Failed for', article.url)

        try:
            article.parse()
        except Exception as e:
            raise Exception(f'Parsing Failed for {article.url}: {e}')

        return article


class Crawl:
    def __init__(self, created_at=None, max_articles=0, status=None, paper_uuid=None):
        self.uuid = uuid.uuid4()
        self.max_articles = max_articles
        self.created_at = created_at
        self.status = status
        self.paper_uuid = paper_uuid
        self.stats = {}

    def __str__(self):
        return 'Crawl of {} on {}. Status {}'.format(self.paper_uuid.split('-')[0], self.created_at, self.status)

    def cache_hit(self):
        from crawler.db.models.DBCrawl import DBCrawl
        return DBCrawl.cache_hit(self)

    def update_status(self, status):
        from crawler.db.models.DBCrawl import DBCrawl
        self.status = status
        DBCrawl.update_status(self, status)
        return True

    def load(self):
        pass

    def save(self):
        from crawler.db.models.DBCrawl import DBCrawl
        return DBCrawl.create(self)

    def close(self):
        from crawler.db.models.DBCrawl import DBCrawl
        return DBCrawl.close()
