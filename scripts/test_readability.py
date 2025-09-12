import json
import os
import requests
from bs4 import BeautifulSoup
import re
import warnings
from urllib.parse import unquote
from random_string_detector import RandomStringDetector
import argparse
import sys
from yarl import URL

# Suppress warnings from BeautifulSoup
warnings.filterwarnings("ignore", category=UserWarning, module='bs4')

# Heuristics for identifying article links
MIN_HEADLINE_LENGTH = 14
MIN_SLUG_LENGTH = 20 # Lowered threshold for decoded Unicode slugs

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

def main():
    """
    Iterates through newspaper_store.json, fetches each category URL,
    and uses BeautifulSoup with heuristics to find likely article links.
    """
    parser = argparse.ArgumentParser(description='Test article link extraction from category pages.')
    parser.add_argument('--accepted-log', nargs='?', const='accepted_logs.txt', default="logs/articles_accepted.txt",
                        help='File to write accepted URLs to. Defaults to accepted_logs.txt.')
    parser.add_argument('--rejected-log', nargs='?', const='rejected_logs.txt', default="logs/articles_rejected.txt",
                        help='File to write rejected URLs to. Defaults to rejected_logs.txt.')
    args = parser.parse_args()

    # Create log directories if they don't exist
    if args.accepted_log:
        log_dir = os.path.dirname(args.accepted_log)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
    if args.rejected_log:
        log_dir = os.path.dirname(args.rejected_log)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

    # Determine output streams (files or stdout)
    accepted_file = None
    if args.accepted_log:
        accepted_file = open(args.accepted_log, 'w', encoding='utf-8')
        print(f"Logging accepted URLs to: {os.path.abspath(args.accepted_log)}")
    else:
        accepted_file = sys.stdout

    rejected_file = None
    if args.rejected_log:
        rejected_file = open(args.rejected_log, 'w', encoding='utf-8')

    accepted_stats = {}
    rejected_stats = {}

    try:
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        json_path = os.path.join(repo_root, 'crawler', 'db', 'newspaper_store.json')

        try:
            with open(json_path, 'r') as f:
                papers_json = json.load(f)
        except FileNotFoundError:
            print(f"Error: Could not find newspaper_store.json at {json_path}", file=accepted_file)
            return
        except json.JSONDecodeError as e:
            print(f"Error: Could not parse newspaper_store.json. Please check for syntax errors.", file=accepted_file)
            print(e, file=accepted_file)
            return

        detector = RandomStringDetector(allow_numbers=True)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'DNT': '1', # Do Not Track
        }

        processed_urls = set() # Global set to track all unique URLs across all papers

        for paper in papers_json:
            paper_url = paper.get('url')
            print(f"\n--- Testing Paper: {paper_url} ---", file=accepted_file)
            if rejected_file:
                print(f"\n--- Testing Paper: {paper_url} ---", file=rejected_file)


            category_urls = paper.get('category_urls', [])
            if not category_urls:
                print("  No category URLs found.", file=accepted_file)
                continue

            for category_url in category_urls:
                print(f"  -> Fetching category: {category_url}", file=accepted_file)
                if rejected_file:
                    print(f"  -> Fetching category: {category_url}", file=rejected_file)

                accepted_stats[category_url] = 0
                rejected_stats[category_url] = 0

                processed_urls_per_category = set()
                try:
                    response = requests.get(category_url, headers=headers, timeout=20)
                    response.raise_for_status()
                    html_content = response.content

                    soup = BeautifulSoup(html_content, 'lxml')
                    all_links = soup.find_all('a')

                    print(f"     - Found {len(all_links)} total links. Applying heuristics...", file=accepted_file)

                    article_links = 0
                    rejected_links = 0
                    for link in all_links:
                        href = link.get('href')
                        if not href: continue

                        title = find_title_for_link(link)

                        try:
                            full_url_obj = URL(requests.compat.urljoin(category_url, href))
                        except ValueError:
                            continue # Skip malformed URLs

                        # Normalize URL by removing query parameters for de-duplication
                        clean_url = str(full_url_obj.with_query(None).with_fragment(None))

                        if clean_url not in processed_urls:
                            processed_urls.add(clean_url)
                            decoded_url = unquote(str(full_url_obj))

                            if is_likely_article(href, title, category_url, detector, whitelist=paper.get('whitelist', [])):
                                accepted_stats[category_url] += 1
                                article_links += 1
                                print(f"{title[:70]:<70} ({decoded_url})", file=accepted_file)
                            elif rejected_file:
                                rejected_stats[category_url] += 1
                                rejected_links += 1
                                print(f"{title[:70]:<70} ({decoded_url})", file=rejected_file)


                    print(f"Identified {article_links} likely article(s).", file=accepted_file)
                    if rejected_file:
                        print(f"Identified {rejected_links} rejected article(s).", file=rejected_file)

                    if article_links == 0:
                        print("No likely article links found.", file=accepted_file)
                    print("\n" + "-" * 30 + "\n", file=accepted_file)

                except requests.exceptions.RequestException as e:
                    print(f"     ! Error fetching URL: {e}", file=accepted_file)
                except Exception as e:
                    print(f"     ! An unexpected error occurred: {e}", file=accepted_file)
    finally:
        if accepted_file is not sys.stdout and accepted_file is not None:
            accepted_file.write("\n\n--- Accepted Links Summary ---\n")
            for url, count in accepted_stats.items():
                accepted_file.write(f"{count}:\t {url}\n")
            accepted_file.close()
            print(f"\nLog summary written to {os.path.abspath(args.accepted_log)}")

        if rejected_file is not None:
            rejected_file.write("\n\n--- Rejected Links Summary ---\n")
            for url, count in rejected_stats.items():
                rejected_file.write(f"{count}:\t {url}\n")
            rejected_file.close()


if __name__ == '__main__':
    main()
