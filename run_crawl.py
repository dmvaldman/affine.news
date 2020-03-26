from Crawler import Crawler
from Paper import Papers

if __name__ == "__main__":
    crawler = Crawler(max_articles=40)

    papers = Papers()
    papers.load()

    crawler.crawl_papers(papers)
