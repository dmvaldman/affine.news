import os
import sys
from dotenv import load_dotenv

# Load .env file from the project root
load_dotenv()

from crawler.services.crawl import get_paper_uuids
from crawler.services.translate import translate_paper_by_uuid


def main():
    """
    Main function to run the translation process for all papers.
    - Fetches all paper UUIDs.
    - Iterates through each paper and translates untranslated articles.
    """
    # These environment variables are required for the script to run.
    required_env_vars = [
        'DATABASE_URL',
        'GOOGLE_PROJECT_ID',
        'GOOGLE_TRANSLATE_API_KEY'
    ]

    missing_vars = [var for var in required_env_vars if not os.environ.get(var)]

    if missing_vars:
        print(f"Error: Missing required environment variables: {', '.join(missing_vars)}", file=sys.stderr)
        sys.exit(1)

    print("Starting translation job...")

    paper_uuids = get_paper_uuids()

    if not paper_uuids:
        print("No papers found in the database to translate.")
        return

    print(f"Found {len(paper_uuids)} papers to process.")

    for paper_uuid in paper_uuids:
        try:
            translate_paper_by_uuid(paper_uuid)
        except Exception as e:
            print(f"An error occurred while processing paper {paper_uuid}: {e}", file=sys.stderr)
            # Continue to the next paper

    print("Translation job finished.")


if __name__ == '__main__':
    main()
