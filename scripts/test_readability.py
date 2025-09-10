import json
import os
import requests
from bs4 import BeautifulSoup
import re
import warnings
from urllib.parse import urlparse, unquote, urlunparse
from random_string_detector import RandomStringDetector
import argparse
import sys

# Suppress warnings from BeautifulSoup
warnings.filterwarnings("ignore", category=UserWarning, module='bs4')

# Heuristics for identifying article links
MIN_HEADLINE_LENGTH = 0
MIN_SLUG_LENGTH = 20 # Lowered threshold for decoded Unicode slugs

def is_likely_article(tag, base_url, detector, whitelist=None):
    """Applies a set of heuristics to determine if a link is a news article."""
    href = tag.get('href')
    text = tag.get_text(strip=True)

    if not href:
        return False

    # If the text is not blank, check that it contains at least one letter.
    # This filters out things like "(22)" or "..." but allows empty titles.
    if text and not any(c.isalpha() for c in text):
        return False

    # 1. Text length check
    if len(text) < MIN_HEADLINE_LENGTH:
        return False

    # 3. Text is not just the URL
    if text.strip() == href.strip():
        return False

    full_url = requests.compat.urljoin(base_url, href)

    def strip_protocol_and_www(url):
        return url.replace('https://', '').replace('http://', '').replace('www.', '')

    # 4. Apply the new path validation logic.
    if whitelist:
        # If a whitelist is present, the URL must start with one of its entries.
        matched = False
        for pattern in whitelist:
            try:
                # For regex, we assume the user will handle protocol agnosticism if needed (e.g., with https?://)
                if re.match(pattern, full_url):
                    matched = True
                    break
            except re.error:
                # Not a valid regex, treat as a prefix, being agnostic to protocol and www
                if strip_protocol_and_www(full_url).startswith(strip_protocol_and_www(pattern)):
                    matched = True
                    break
        if not matched:
            return False
    else:
        # If no whitelist, URL must be an extension of the category_url, being agnostic to protocol and www.
        if not strip_protocol_and_www(full_url).startswith(strip_protocol_and_www(base_url)):
            return False

    # 5. Check if the link belongs to the same domain by comparing the 'netloc'.
    try:
        base_domain = urlparse(base_url).netloc.replace('www.', '')
        link_domain = urlparse(full_url).netloc.replace('www.', '')
        if base_domain != link_domain:
            return False
    except Exception:
        # If urlparse fails for any reason, conservatively reject the link
        return False

    # 5. After confirming domain, check for common article URL patterns.
    path = urlparse(full_url).path
    slug = path.rstrip('/').split('/')[-1]
    decoded_slug = unquote(slug)

    if not (
        re.search(r'\.(s?html?)$', path) or
        re.search(r'(/\d{4}/\d{1,2}[/-]\d{1,2}/|\d{4}-\d{1,2}-\d{1,2})', path) or
        re.search(r'\d{6,}', path) or
        len(decoded_slug) > MIN_SLUG_LENGTH or
        detector(slug) # Use the new random string detector
    ):
        return False

    return True

def main():
    """
    Iterates through newspaper_store.json, fetches each category URL,
    and uses BeautifulSoup with heuristics to find likely article links.
    """
    parser = argparse.ArgumentParser(description='Test article link extraction from category pages.')
    parser.add_argument('--accepted-log', nargs='?', const='accepted_logs.txt', default="articles_accepted.txt",
                        help='File to write accepted URLs to. Defaults to accepted_logs.txt.')
    parser.add_argument('--rejected-log', nargs='?', const='rejected_logs.txt', default="articles_rejected.txt",
                        help='File to write rejected URLs to. Defaults to rejected_logs.txt.')
    args = parser.parse_args()

    # Determine output streams (files or stdout)
    accepted_file = None
    if args.accepted_log:
        accepted_file = open(args.accepted_log, 'w', encoding='utf-8')
    else:
        accepted_file = sys.stdout # Default to printing accepted to console

    rejected_file = None
    if args.rejected_log:
        rejected_file = open(args.rejected_log, 'w', encoding='utf-8')


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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
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
            processed_urls_per_category = set()
            try:
                response = requests.get(category_url, headers=headers, timeout=15)
                response.raise_for_status()
                html_content = response.content

                soup = BeautifulSoup(html_content, 'lxml')
                all_links = soup.find_all('a')

                print(f"     - Found {len(all_links)} total links. Applying heuristics...", file=accepted_file)

                article_links = 0
                rejected_links = 0
                for link in all_links:
                    href = link.get('href')
                    title = link.get_text(strip=True)
                    full_url = requests.compat.urljoin(category_url, href)

                    # Normalize URL by removing query parameters for de-duplication
                    parsed_url = urlparse(full_url)
                    clean_url = urlunparse(parsed_url._replace(query="", fragment=""))

                    if clean_url not in processed_urls:
                        processed_urls.add(clean_url)
                        decoded_url = unquote(full_url)

                        if is_likely_article(link, category_url, detector, whitelist=paper.get('whitelist', [])):
                            article_links += 1
                            print(f"{title[:70]:<70} ({decoded_url})", file=accepted_file)
                        elif rejected_file:
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

    if args.accepted_log and accepted_file:
        accepted_file.close()
        print(f"\nAccepted URLs written to {args.accepted_log}")

    if args.rejected_log and rejected_file:
        rejected_file.close()
        print(f"Rejected URLs written to {args.rejected_log}")


if __name__ == '__main__':
    main()
