from server.models.Crawler import Crawler
from server.models.Paper import Papers


def run(max_articles=1):
    crawler = Crawler(max_articles=max_articles)
    papers = Papers()
    papers.load()
    crawler.crawl_papers(papers)
