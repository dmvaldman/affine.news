from crawler.models.Crawler import Crawler
from crawler.models.Paper import Paper, Papers


def get_paper_uuids():
    papers = Papers()
    papers.load()

    uuids = [paper.uuid for paper in papers]
    return uuids


def crawl_paper_by_url(url, max_articles=1):
    paper = Paper.load_from_url(url)
    crawler = Crawler(max_articles=max_articles)
    return crawler.crawl_paper(paper)


def crawl_paper_by_uuid(uuid, max_articles=1):
    crawler = Crawler(max_articles=max_articles)
    paper = Paper.load_from_uuid(uuid)
    return crawler.crawl_paper(paper)


def run(max_articles=1):
    crawler = Crawler(max_articles=max_articles)
    papers = Papers()
    papers.load()

    for paper in papers:
        crawler.crawl_paper(paper)
