import argparse
import os
import sys
import nltk
import time
from dotenv import load_dotenv

load_dotenv()

# Download 'punkt' tokenizer if needed, but do it quietly.
try:
    nltk.data.find('tokenizers/punkt')
except nltk.downloader.DownloadError:
    nltk.download('punkt', quiet=True)

from crawler.services.crawl import get_papers, crawl_paper

def main():
    parser = argparse.ArgumentParser(description='Run crawler over papers')
    parser.add_argument('--max-articles', type=int, default=5)
    parser.add_argument('--ignore-cache', action='store_true', default=False)
    args = parser.parse_args()

    if not os.environ.get('DATABASE_URL'):
        print('DATABASE_URL env is required', file=sys.stderr)
        sys.exit(1)

    overall_start_time = time.time()
    papers = get_papers()
    all_stats = []
    total_downloaded = 0
    total_failed = 0

    for paper in papers:
        paper_start_time = time.time()
        crawl_result = crawl_paper(paper, max_articles=args.max_articles, ignore_cache=args.ignore_cache)
        paper_elapsed_time = time.time() - paper_start_time

        if crawl_result and crawl_result.stats:
            downloaded = crawl_result.stats.get('downloaded', 0)
            failed = crawl_result.stats.get('failed', 0)

            # Since we don't have the paper object here, we'll use the UUID for the report
            all_stats.append({
                "id": paper.uuid[:8], # Use a shortened UUID for readability
                "downloaded": downloaded,
                "failed": failed,
                "elapsed": paper_elapsed_time
            })
            total_downloaded += downloaded
            total_failed += failed

    print("\n--- Crawl Summary ---")
    print(f"{'Paper ID':<10} {'Downloaded':<12} {'Failed':<8} {'Time (s)':<10}")
    print("-" * 50)
    for stats in all_stats:
        print(f"{stats['id']:<10} {stats['downloaded']:<12} {stats['failed']:<8} {stats['elapsed']:.2f}")

    print("\n--- Totals ---")
    total_articles = total_downloaded + total_failed
    success_rate = (total_downloaded / total_articles * 100) if total_articles > 0 else 0
    print(f"Total Articles Downloaded: {total_downloaded}")
    print(f"Total Articles Failed: {total_failed}")
    print(f"Success Rate: {success_rate:.2f}%")

    overall_elapsed_time = time.time() - overall_start_time
    print(f"Total Time Elapsed: {overall_elapsed_time:.2f} seconds")


if __name__ == '__main__':
    main()


