import requests
from bs4 import BeautifulSoup
import re
import warnings
from urllib.parse import unquote
from random_string_detector import RandomStringDetector
import argparse
from yarl import URL
from datetime import date
import json
import gzip
import zstandard
import os

from crawler.models.Article import Article
from crawler.models.Paper import Papers, Paper
# Suppress warnings from BeautifulSoup
warnings.filterwarnings("ignore", category=UserWarning, module='bs4')

# Heuristics for identifying article links
MIN_HEADLINE_LENGTH = 14
MIN_SLUG_LENGTH = 20

def find_title_for_link(tag):
    """
    Finds the best title for a link by looking at the text of the link itself
    and all of its direct siblings, returning whichever is longest.
    """
    # Base case for recursion to prevent errors at the top of the DOM tree
    if not tag:
        return ""

    # Prioritize the link's own text if it's a decent length
    best_text = tag.get_text(strip=True, separator=' ')
    if len(best_text) > 12:
        return best_text

    if tag.parent:
        # Check siblings for a better title, and return immediately if a good one is found.
        for sibling in tag.parent.find_all(recursive=False):
            sibling_text = sibling.get_text(strip=True, separator=' ')
            if len(sibling_text) > len(best_text):
                best_text = sibling_text

        # If, after checking all siblings, we still have a very short title, recurse.
        if len(best_text) < 12:
          return find_title_for_link(tag.parent)

    return best_text


def decompress_content(resp, verbose=False):
    """
    Checks for and handles compressed content (zstd, gzip)
    when the Content-Encoding header is missing.
    """
    content = resp.content
    if resp.headers.get('Content-Encoding') is None:
        try:
            # Check for zstandard magic number: b'(\\xb5/\\xfd'
            if content.startswith(b'\x28\xb5\x2f\xfd'):
                if verbose:
                    print("  -> Manually decompressing zstandard content...")
                dctx = zstandard.ZstdDecompressor()
                return dctx.decompress(content)
            # Check for gzip magic number
            elif content.startswith(b'\x1f\x8b'):
                if verbose:
                    print("  -> Manually decompressing gzip content...")
                return gzip.decompress(content)
            else:
                print("  -> Unknown content encoding")
        except Exception as e:
            if verbose:
                print(f"  ! Manual decompression failed: {e}")
            # Fallback to original content on error
            return content
    return content


def is_likely_article(href, text, base_url, detector, whitelist=None):
    """Applies a set of heuristics to determine if a link is a news article."""
    if not href:
        return False

    # If the text is not blank, check that it contains at least one letter.
    if text and not any(c.isalpha() for c in text):
        return False

    # 1. Text length check
    if len(text) < MIN_HEADLINE_LENGTH:
        return False

    try:
        base_url_obj = URL(base_url)
        full_url_obj = URL(requests.compat.urljoin(base_url, href))
    except ValueError:
        return False # Invalid URL

    # Early exit for root domains or URLs identical to the category page.
    if not full_url_obj.path or full_url_obj.path == '/' or full_url_obj == base_url_obj:
        return False

    def normalize_host(host):
        """Normalizes a host string by removing 'www.'."""
        if host is None:
            return ''
        return host.replace('www.', '')

    def get_comparable_url_string(url_obj):
        """Returns a string representation of the URL without protocol and www for prefix matching."""
        return normalize_host(url_obj.host) + url_obj.path_qs

    # 4. Path Validation Logic:
    # A whitelist match is a definitive "yes". Check this first.
    if whitelist:
        full_url_str = str(full_url_obj)
        for pattern in whitelist:
            try:
                if re.match(pattern, full_url_str):
                    return True # Whitelist match = instant pass
            except re.error:
                comparable_full_url = get_comparable_url_string(full_url_obj)
                comparable_pattern = get_comparable_url_string(URL(pattern))
                if comparable_full_url.startswith(comparable_pattern):
                    return True # Whitelist match = instant pass

    # If no whitelist match, check if it's a valid extension of the category URL.
    is_valid_extension = get_comparable_url_string(full_url_obj).startswith(get_comparable_url_string(base_url_obj))
    if not is_valid_extension:
        return False # Fails category check and didn't match whitelist

    # 5. Check if the link belongs to the same domain by comparing the 'netloc'.
    base_domain = normalize_host(base_url_obj.host)
    link_domain = normalize_host(full_url_obj.host)
    if base_domain != link_domain:
        return False

    # After confirming domain, check for common article URL patterns.
    path = full_url_obj.path
    slug = path.rstrip('/').split('/')[-1]
    if not slug: return False
    decoded_slug = unquote(slug)

    # Simplified Category URL Heuristic:
    # A URL is likely a category page if its slug is short and non-random,
    # and the overall URL is not much longer than the base category URL.
    is_short_low_entropy_slug = len(decoded_slug) < 16 and not detector(decoded_slug)
    is_short_overall_url = len(str(full_url_obj)) < (len(base_url) * 2)

    if is_short_low_entropy_slug and is_short_overall_url:
        # Override: If a date is in the path, it's probably an article, not a category page.
        if not re.search(r'(/\d{4}/\d{1,2}[/-]\d{1,2}/|\d{4}-\d{1,2}-\d{1,2})', path):
            return False

    # If it doesn't look like a category slug, check for other strong article indicators.
    if (re.search(r'\.(s?html?)$', path) or
        re.search(r'(/\d{4}/\d{1,2}[/-]\d{1,2}/|\d{4}-\d{1,2}-\d{1,2})', path) or
        re.search(r'\d{6,}', path) or
        len(decoded_slug) > MIN_SLUG_LENGTH or
        detector(slug)):
        return True

    # Default to rejecting if no strong signals are found.
    return False

class HeuristicCrawler:
    def __init__(self, max_articles=None):
        self.max_articles = max_articles

    def crawl_paper(self, paper, verbose=True, ignore_cache=False):
        if verbose:
            print('HeuristicCrawler building', paper)

        todays_date = date.today()

        # Stats
        count_success = 0
        count_rejected = 0
        count_cache_hits = 0

        accepted_links_by_category = {}
        rejected_links_by_category = {}

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'DNT': '1',
        }

        seen_urls = set()
        detector = RandomStringDetector(allow_numbers=True)

        for category_url in getattr(paper, 'category_urls', []) or []:
            accepted_links_by_category[category_url] = []
            rejected_links_by_category[category_url] = []

            try:
                resp = requests.get(category_url, headers=headers, timeout=20)
                resp.raise_for_status()

                content = decompress_content(resp, verbose=verbose)

            except requests.exceptions.RequestException as e:
                if verbose:
                    print(f"! Error fetching {category_url}: {e}")
                continue

            soup = BeautifulSoup(content, 'lxml')
            links = soup.find_all('a')

            for link in links:
                if self.max_articles is not None and count_success >= self.max_articles:
                    break

                href = link.get('href')
                if not href:
                    continue

                title = find_title_for_link(link)
                try:
                    full_url_obj = URL(requests.compat.urljoin(category_url, href))
                except ValueError:
                    continue

                # Normalize the URL for cache checking by removing query params and fragments
                url_normalized = str(full_url_obj.with_query(None).with_fragment(None))
                if url_normalized in seen_urls:
                    continue
                seen_urls.add(url_normalized)

                if is_likely_article(href, title, category_url, detector, whitelist=getattr(paper, 'whitelist', [])):
                    accepted_links_by_category[category_url].append(url_normalized)

                    article = Article(
                        url=url_normalized,
                        title=title,
                        img_url='',
                        publish_at=todays_date,
                        lang=getattr(paper, 'lang', ''),
                        paper_uuid=paper.uuid
                    )

                    if not ignore_cache and article.cache_hit():
                        count_cache_hits += 1
                        if verbose:
                            print('Article cache hit', article)
                        continue

                    print('Scraped', article)

                    article.save()
                    count_success += 1
                else:
                    rejected_links_by_category[category_url].append(url_normalized)
                    count_rejected += 1

                if self.max_articles is not None and count_success >= self.max_articles:
                    break

        stats = {}
        stats['downloaded'] = count_success
        stats['rejected'] = count_rejected
        stats['cache_hits'] = count_cache_hits
        stats['accepted'] = count_success + count_cache_hits
        stats['accepted_links'] = accepted_links_by_category
        stats['rejected_links'] = rejected_links_by_category
        return stats


def main():
    """
    Iterates through all papers in the database and runs the HeuristicCrawler on each.
    """
    parser = argparse.ArgumentParser(description='Run HeuristicCrawler over papers.')
    parser.add_argument('--max-articles', type=int, default=None,
                        help='Maximum number of articles to find per paper.')
    parser.add_argument('--ignore-cache', action='store_true', default=False,
                        help='Ignore cache and re-crawl papers.')
    parser.add_argument('--log-to-file', action='store_true', default=False,
                        help='Log accepted and rejected links to files.')
    args = parser.parse_args()

    accepted_log_file = None
    rejected_log_file = None
    if args.log_to_file:
        # Ensure the logs directory exists
        os.makedirs('logs', exist_ok=True)
        accepted_log_file = open('logs/accepted_links.txt', 'w')
        rejected_log_file = open('logs/rejected_links.txt', 'w')

    all_crawl_stats = []

    # Load papers directly from the JSON file to bypass the database
    papers = []
    with open('crawler/db/newspaper_store.json', 'r') as f:
        papers_data = json.load(f)
        for paper_data in papers_data:
            # get uuid
            paperDB = Paper.load_from_url(paper_data['url'])
            if not paperDB:
                print(f"Paper not found: {paper_data['url']}")
                continue
            paper_data['uuid'] = paperDB.uuid
            papers.append(Paper(**paper_data))

    crawler = HeuristicCrawler(max_articles=args.max_articles)

    for paper in papers:
        print(f"\n--- Starting Heuristic Crawl for: {paper.url} ---")
        try:
            crawl_result = crawler.crawl_paper(
                paper,
                ignore_cache=args.ignore_cache,
            )

            if args.log_to_file:
                if accepted_log_file:
                    accepted_links_by_cat = crawl_result.get('accepted_links', {})
                    for category_url, links in accepted_links_by_cat.items():
                        if links:
                            accepted_log_file.write(f"\n{paper.country}, {paper.url}, {category_url}\n")
                            accepted_log_file.write("\n".join(links))
                            accepted_log_file.write(f"\ntotal accepted: {len(links)}\n")
                if rejected_log_file:
                    rejected_links_by_cat = crawl_result.get('rejected_links', {})
                    for category_url, links in rejected_links_by_cat.items():
                        if links:
                            rejected_log_file.write(f"\n{paper.country}, {paper.url}, {category_url}\n")
                            rejected_log_file.write("\n".join(links))
                            rejected_log_file.write(f"\ntotal rejected: {len(links)}\n")

            if crawl_result:
                downloaded = crawl_result.get('downloaded', 0)
                rejected = crawl_result.get('rejected', 0)
                cache_hits = crawl_result.get('cache_hits', 0)
                accepted = crawl_result.get('accepted', 0)
                print(f"  -> Finished: {accepted} articles accepted ({downloaded} new, {cache_hits} cache hits), {rejected} links rejected.")
                all_crawl_stats.append({'paper': paper, 'stats': crawl_result})
            else:
                print("  -> Crawl returned no result.")
        except Exception as e:
            print(f"  -> An unexpected error occurred: {e}")

    if args.log_to_file:
        if accepted_log_file:
            accepted_log_file.write("\n\n--- AGGREGATE STATS (ACCEPTED) ---\n")
            for item in sorted(all_crawl_stats, key=lambda x: x['paper'].country):
                paper = item['paper']
                stats = item['stats']
                accepted_log_file.write(f"{paper.country}, {paper.url}, {stats.get('accepted', 0)}\n")
            accepted_log_file.close()
        if rejected_log_file:
            rejected_log_file.write("\n\n--- AGGREGATE STATS (REJECTED) ---\n")
            for item in sorted(all_crawl_stats, key=lambda x: x['paper'].country):
                paper = item['paper']
                stats = item['stats']
                rejected_log_file.write(f"{paper.country}, {paper.url}, {stats.get('rejected', 0)}\n")
            rejected_log_file.close()

def main_single():
    # paper_info = {
    #     "country": "Albania",
    #     "ISO": "ALB",
    #     "lang": "sq",
    #     "url": "https://www.gazetatema.net/",
    #     "category_urls": [
    #         "https://www.gazetatema.net/category/bota/"
    #     ],
    #     "whitelist": [
    #         "https://www.gazetatema.net/bota/"
    #     ]
    # }

    # paper_info = {
    #     "country": "Albania",
    #     "ISO": "ALB",
    #     "lang": "sq",
    #     "url": "https://www.balkanweb.com/",
    #     "category_urls": [
    #         "https://www.balkanweb.com/kategoria/bota/"
    #     ],
    #     "whitelist": [
    #         "^https://www.balkanweb.com/[^/]+/?$"
    #     ]
    # }

    # paper_info = {
    #     "country": "Austria",
    #     "ISO": "AUT",
    #     "lang": "de",
    #     "url": "https://www.diepresse.com/",
    #     "category_urls": [
    #         "https://www.diepresse.com/ausland"
    #     ],
    #     "whitelist": [
    #         "^https://www.diepresse.com/\\d+/"
    #     ]
    # }

    # paper_info = {
    #     "country": "Belarus",
    #     "ISO": "BLR",
    #     "lang": "ru",
    #     "url": "https://nashaniva.com/",
    #     "category_urls": [
    #         "https://nashaniva.com/?c=ca&i=584"
    #     ],
    #     "whitelist": [
    #         "^https://nashaniva.com/\\d+$"
    #     ]
    # }

    # paper_info = {
    #     "country": "Bolivia",
    #     "ISO": "BOL",
    #     "lang": "es",
    #     "url": "https://eldeber.com.bo/",
    #     "category_urls": [
    #         "https://eldeber.com.bo/mundo/"
    #     ],
    #     "whitelist": [
    #         "https://eldeber.com.bo/bbc/"
    #     ]
    # }

    # paper_info = {
    #     "country": "Bolivia",
    #     "ISO": "BOL",
    #     "lang": "es",
    #     "url": "https://www.larazon.bo/",
    #     "category_urls": [
    #         "https://www.larazon.bo/mundo/"
    #     ]
    # }

    paper_info = {
        "country": "Chile",
        "ISO": "CHL",
        "lang": "es",
        "url": "https://www.latercera.com/",
        "category_urls": [
            "https://www.latercera.com/mundo/"
        ]
    }

    # paper_info = {
    #     "country": "Kenya",
    #     "ISO": "KEN",
    #     "lang": "en",
    #     "url": "https://www.standardmedia.co.ke/",
    #     "category_urls": [
    #         "https://www.standardmedia.co.ke/category/5/world"
    #     ],
    #     "whitelist": [
    #         "https://www.standardmedia.co.ke/world/",
    #         "https://www.standardmedia.co.ke/europe/",
    #         "https://www.standardmedia.co.ke/asia/",
    #         "https://www.standardmedia.co.ke/africa/",
    #         "https://www.standardmedia.co.ke/america/"
    #     ]
    # }

    # paper_info = {
    #     "country": "Malaysia",
    #     "ISO": "MYS",
    #     "lang": "en",
    #     "url": "https://www.thestar.com.my/",
    #     "category_urls": [
    #         "https://www.thestar.com.my/news/world/"
    #     ]
    # }

    # paper_info = {
    #     "country": "Malaysia",
    #     "ISO": "MYS",
    #     "lang": "ms",
    #     "url": "https://www.bharian.com.my/",
    #     "category_urls": [
    #         "https://www.bharian.com.my/dunia"
    #     ]
    # }

    # paper_info = {
    #     "country": "Mongolia",
    #     "ISO": "MNG",
    #     "lang": "mn",
    #     "url": "https://eguur.mn/",
    #     "category_urls": [
    #         "https://eguur.mn/news/world/https://eguur.mn/category/%d0%b4%d1%8d%d0%bb%d1%85%d0%b8%d0%b9/"
    #     ],
    #     "whitelist": [
    #         "^https://eguur.mn/\\d+/"
    #     ]
    # }

    # paper_info = {
    #     "country": "Myanmar",
    #     "ISO": "MMR",
    #     "lang": "en",
    #     "url": "https://www.irrawaddy.com/",
    #     "category_urls": [
    #         "https://www.irrawaddy.com/category/news/world"
    #     ]
    # }

    # paper_info = {
    #     "country": "Pakistan",
    #     "ISO": "PAK",
    #     "lang": "ur",
    #     "url": "https://www.jang.com.pk/",
    #     "category_urls": [
    #         "https://www.jang.com.pk/category/latest-news/world"
    #     ],
    #     "whitelist": [
    #         "https://www.jang.com.pk/news/"
    #     ]
    # }

    # paper_info = {
    #     "country": "Panama",
    #     "ISO": "PAN",
    #     "lang": "es",
    #     "url": "https://www.prensa.com/",
    #     "category_urls": [
    #         "https://www.prensa.com/mundo/"
    #     ]
    # }

    # paper_info = {
    #     "country": "Poland",
    #     "ISO": "POL",
    #     "lang": "pl",
    #     "url": "https://wyborcza.pl/",
    #     "category_urls": [
    #         "https://wyborcza.pl/0,75399.html"
    #     ],
    #     "whitelist": [
    #         "^https://wyborcza.pl/\\d+,\\d+,\\d+,\\d+,\\d+\\.html#s=S.index-K.C-B.1-L.\\d+\\.duzy$"
    #     ]
    # }

    # paper_info = {
    #     "country": "Ukraine",
    #     "ISO": "UKR",
    #     "lang": "uk",
    #     "url": "https://fakty.ua/",
    #     "category_urls": [
    #         "https://fakty.ua/categories/world"
    #     ],
    #     "whitelist": [
    #         "^https://fakty.ua/\\d{6}-.*"
    #     ]
    # }

    # paper_info = {
    #     "country": "Ukraine",
    #     "ISO": "UKR",
    #     "lang": "uk",
    #     "url": "https://www.kyivpost.com",
    #     "category_urls": [
    #     "https://www.kyivpost.com/category/world"
    #     ],
    #     "whitelist": [
    #         "https://www.kyivpost.com/post/",
    #         "https://www.kyivpost.com/topic/"
    #     ]
    # }

    # paper_info = {
    #     "country": "United States",
    #     "ISO": "USA",
    #     "lang": "en",
    #     "url": "https://www.washingtonpost.com/",
    #     "category_urls": [
    #         "https://www.washingtonpost.com/world/"
    #     ]
    # }

    # paper_info = {
    #     "country": "Venezuela",
    #     "ISO": "VEN",
    #     "lang": "es",
    #     "url": "https://www.elnacional.com/",
    #     "category_urls": [
    #         "https://www.elnacional.com/mundo/"
    #     ],
    #     "whitelist": [
    #         "^https://www.elnacional.com/\\d{4}/\\d{2}/.+"
    #     ]
    # }

    # paper_info = {
    #     "country": "Venezuela",
    #     "ISO": "VEN",
    #     "lang": "es",
    #     "url": "https://www.eluniversal.com/",
    #     "category_urls": [
    #         "https://www.eluniversal.com/internacional"
    #     ]
    # }

    # paper_info = {
    #     "country": "Yemen",
    #     "ISO": "YEM",
    #     "lang": "ar",
    #     "url": "https://www.sabanew.net/",
    #     "category_urls": [
    #         "https://www.sabanew.net/category/ar/1/"
    #     ],
    #     "whitelist": [
    #         "https://www.sabanew.net/story/ar/"
    #     ]
    # }

    # paper_info = {
    #     "country": "Serbia",
    #     "ISO": "SRB",
    #     "lang": "sr",
    #     "url": "https://www.politika.rs/",
    #     "category_urls": [
    #         "https://www.politika.rs/scc/svet"
    #     ],
    #     "whitelist": [
    #         "https://www.politika.rs/scc/"
    #     ]
    # }

    # paper_info = {
    #     "country": "Nicaragua",
    #     "ISO": "NIC",
    #     "lang": "es",
    #     "url": "https://www.laprensani.com/",
    #     "category_urls": [
    #         "https://www.laprensani.com/seccion/internacionales/"
    #     ]
    # }

    paper_info['uuid'] = Paper.load_from_url(paper_info['url']).uuid
    paper = Paper(**paper_info)
    crawler = HeuristicCrawler(max_articles=20)
    crawl_result = crawler.crawl_paper(paper)
    print(crawl_result)

if __name__ == '__main__':
    main()
    # main_single()
