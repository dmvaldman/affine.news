import argparse
import hashlib
import json
import os
import sys

import psycopg2


def stable_uuid_from_url(url: str) -> str:
    return hashlib.md5(url.encode('utf-8')).hexdigest()


def main():
    parser = argparse.ArgumentParser(description='Sync newspaper_store.json to DB')
    parser.add_argument('--prune-missing', action='store_true', help='Delete categories not present in JSON for each paper')
    parser.add_argument('--dry-run', action='store_true', help='Show actions without writing')
    args = parser.parse_args()

    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print('DATABASE_URL is not set', file=sys.stderr)
        sys.exit(1)

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    json_path = os.path.join(repo_root, 'server', 'db', 'newspaper_store.json')
    with open(json_path, 'r') as f:
        papers_json = json.load(f)

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as c:
            for paper_json in papers_json:
                paper_uuid = stable_uuid_from_url(paper_json['url'])
                if args.dry_run:
                    print(f"UPSERT paper {paper_json['url']} -> uuid {paper_uuid}")
                else:
                    c.execute(
                        """
                        INSERT INTO paper (uuid, url, country, ISO, lang)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (uuid) DO UPDATE SET url = EXCLUDED.url,
                                                      country = EXCLUDED.country,
                                                      ISO = EXCLUDED.ISO,
                                                      lang = EXCLUDED.lang
                        """,
                        (paper_uuid, paper_json['url'], paper_json['country'], paper_json['ISO'], paper_json['lang'])
                    )

                if args.prune_missing:
                    if args.dry_run:
                        print(f"PRUNE categories not in JSON for paper {paper_uuid}")
                    else:
                        tuple_list = tuple(paper_json['category_urls']) or ('',)
                        c.execute("DELETE FROM category_set WHERE paper_uuid = %s AND url NOT IN %s",
                                  (paper_uuid, tuple_list))

                for url in paper_json['category_urls']:
                    if args.dry_run:
                        print(f"UPSERT category {url} for paper {paper_uuid}")
                    else:
                        c.execute(
                            """
                            INSERT INTO category_set (paper_uuid, url)
                            VALUES (%s, %s)
                            ON CONFLICT ON CONSTRAINT uq_category_set_paper_url DO NOTHING
                            """,
                            (paper_uuid, url)
                        )

        if args.dry_run:
            print('Dry run complete (no changes written)')
            conn.rollback()
        else:
            conn.commit()
            print('Sync complete')
    finally:
        conn.close()


if __name__ == '__main__':
    main()


