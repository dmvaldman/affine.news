import requests
from bs4 import BeautifulSoup
import re
import warnings
from urllib.parse import unquote
from random_string_detector import RandomStringDetector
import argparse
from yarl import URL
from datetime import date

from crawler.models.Article import Article
from crawler.models.Paper import Papers
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
    if len(best_text) > 4:
        return best_text

    if tag.parent:
        # Check siblings for a better title, and return immediately if a good one is found.
        for sibling in tag.parent.find_all(recursive=False):
            sibling_text = sibling.get_text(strip=True, separator=' ')
            if len(sibling_text) > len(best_text):
                best_text = sibling_text

        # If, after checking all siblings, we still have a very short title, recurse.
        if len(best_text) < 5:
          return find_title_for_link(tag.parent)

    return best_text


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

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'DNT': '1',
        }

        processed_urls = set()
        detector = RandomStringDetector(allow_numbers=True)

        for category_url in getattr(paper, 'category_urls', []) or []:
            try:
                resp = requests.get(category_url, headers=headers, timeout=20)
                resp.raise_for_status()
            except requests.exceptions.RequestException as e:
                if verbose:
                    print(f"! Error fetching {category_url}: {e}")
                continue

            soup = BeautifulSoup(resp.content, 'lxml')
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

                clean_url = str(full_url_obj.with_query(None).with_fragment(None))
                if clean_url in processed_urls:
                    continue
                processed_urls.add(clean_url)

                decoded_url = unquote(str(full_url_obj))
                if is_likely_article(href, title, category_url, detector, whitelist=getattr(paper, 'whitelist', [])):
                    # Build Article with today's date and no img
                    article = Article(
                        url=decoded_url,
                        title=title,
                        img_url='',
                        publish_at=todays_date,
                        lang=getattr(paper, 'lang', ''),
                        paper_uuid=paper.uuid
                    )

                    if not ignore_cache and article.cache_hit():
                        if verbose:
                            print('Article cache hit', article)
                        continue

                    article.save()
                    count_success += 1
                else:
                    count_rejected += 1

                if self.max_articles is not None and count_success >= self.max_articles:
                    break

        stats = {}
        stats['downloaded'] = count_success
        stats['failed'] = count_rejected
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
    args = parser.parse_args()

    papers = Papers().load()
    crawler = HeuristicCrawler(max_articles=args.max_articles)

    for paper in papers:
        print(f"\n--- Starting Heuristic Crawl for: {paper.url} ---")
        try:
            crawl_result = crawler.crawl_paper(paper, ignore_cache=args.ignore_cache)
            if crawl_result:
                downloaded = crawl_result.get('downloaded', 0)
                rejected = crawl_result.get('failed', 0) # 'failed' is 'rejected' in this context
                print(f"  -> Finished: {downloaded} articles accepted, {rejected} links rejected.")
            else:
                print("  -> Crawl returned no result.")
        except Exception as e:
            print(f"  -> An unexpected error occurred: {e}")

if __name__ == '__main__':
    main()
