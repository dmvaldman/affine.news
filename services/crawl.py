from Crawler import Crawler
from Paper import Papers

def run(max_articles=40):
    crawler = Crawler(max_articles=max_articles)
    papers = Papers()
    papers.load()
    crawler.crawl_papers(papers)
