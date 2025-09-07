import argparse
import os
import sys

from server.services.crawl import get_paper_uuids, crawl_paper_by_uuid


def main():
    parser = argparse.ArgumentParser(description='Run crawler over papers')
    parser.add_argument('--max-articles', type=int, default=30)
    args = parser.parse_args()

    if not os.environ.get('DATABASE_URL'):
        print('DATABASE_URL env is required', file=sys.stderr)
        sys.exit(1)

    uuids = get_paper_uuids()
    for paper_uuid in uuids:
        crawl_paper_by_uuid(paper_uuid, max_articles=args.max_articles)


if __name__ == '__main__':
    main()


