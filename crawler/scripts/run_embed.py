import sys
from crawler.db.db import conn
from crawler.services.embedding import get_embeddings


BATCH_SIZE = 100 # Gemini API allows up to 100 contents per request

def main():
    """
    Fetches articles without embeddings, generates embeddings for their titles,
    and updates the database.
    """

    try:
        with conn.cursor() as cur:
            cur.execute("""
              SELECT url, title_translated FROM article
              WHERE title_embedding IS NULL
              AND title_translated IS NOT NULL
              AND title_translated != ''
              AND publish_at >= NOW() - INTERVAL '2 days'
            """)
            articles_to_embed = cur.fetchall()

        print(f"Found {len(articles_to_embed)} articles to embed.")

        for i in range(0, len(articles_to_embed), BATCH_SIZE):
            batch = articles_to_embed[i:i + BATCH_SIZE]
            urls = [item[0] for item in batch]
            titles = [item[1] for item in batch]

            print(f"Processing batch {i//BATCH_SIZE + 1} with {len(titles)} titles...")
            embeddings = get_embeddings(titles)

            if not embeddings or len(embeddings) != len(batch):
                print(f"Warning: Could not generate embeddings for batch starting at index {i}. Skipping.", file=sys.stderr)
                continue

            with conn.cursor() as cur:
                for url, embedding in zip(urls, embeddings):
                    cur.execute(
                        "UPDATE article SET title_embedding = %s WHERE url = %s",
                        (embedding, url)
                    )
            conn.commit()
            print(f"Successfully updated {len(batch)} articles.")

    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
    finally:
        if conn:
            conn.close()
        print("Embedding job finished.")

if __name__ == "__main__":
    main()
