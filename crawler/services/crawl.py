from crawler.models.Crawler import Crawler
from crawler.models.Paper import Paper, Papers

def get_papers() -> Papers:
    papers = Papers()
    papers.load()
    return papers

def crawl_paper(paper: Paper, max_articles=None, ignore_cache=False):
    crawler = Crawler(max_articles=max_articles)
    return crawler.crawl_paper(paper, ignore_cache=ignore_cache)