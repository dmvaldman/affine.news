import os
import sys
import time
from dotenv import load_dotenv

# Load .env file from the project root
load_dotenv()

from crawler.services.translate import translate_paper, get_papers


def main():
    """
    Main function to run the translation process for all papers.
    - Fetches all paper UUIDs.
    - Iterates through each paper and translates untranslated articles.
    """
    start_time = time.time()
    # These environment variables are required for the script to run.
    required_env_vars = [
        'DATABASE_URL',
        'GOOGLE_PROJECT_ID',
    ]

    missing_vars = [var for var in required_env_vars if not os.environ.get(var)]

    if missing_vars:
        print(f"Error: Missing required environment variables: {', '.join(missing_vars)}", file=sys.stderr)
        sys.exit(1)

    print("Starting translation job...")

    papers = get_papers()

    if not papers:
        print("No papers found in the database to translate.")
        return

    print(f"Found {len(papers)} papers to process.")

    for paper in papers:
        try:
            translate_paper(paper)
        except Exception as e:
            print(f"An error occurred while processing paper {paper}: {e}", file=sys.stderr)
            # Continue to the next paper

    end_time = time.time()
    print("Translation job finished.")
    print(f"Total time elapsed: {end_time - start_time:.2f} seconds")


if __name__ == '__main__':
    main()
