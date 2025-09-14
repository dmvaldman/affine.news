import os
import sys
import psycopg2
from pgvector.psycopg2 import register_vector
import numpy as np
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from bertopic import BERTopic

# Add crawler directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from db.db import conn
from services.topic_generator import generate_topics


def main():
    """
    Fetches recent articles, runs BERTopic to find topics, uses Gemini to generate
    clean topic labels, and saves them to the database and a JSON file.
    """
    load_dotenv()
    try:
        if conn is None:
            print("Could not connect to the database. Exiting.", file=sys.stderr)
            sys.exit(1)

        register_vector(conn)

        two_days_ago = datetime.now() - timedelta(days=2)
        print(f"Fetching articles from the last 2 days (since {two_days_ago.strftime('%Y-%m-%d')})...")

        with conn.cursor() as cur:
            cur.execute(
                "SELECT title_translated, title_embedding FROM article WHERE publish_at >= %s AND title_embedding IS NOT NULL AND title_translated IS NOT NULL AND title_translated != ''",
                (two_days_ago,)
            )
            results = cur.fetchall()

        if not results:
            print("No articles with embeddings found in the last 2 days.")
            return

        print(f"Found {len(results)} articles to process.")
        titles = [row[0] for row in results]
        embeddings = np.array([row[1] for row in results])

        print("Initializing and running BERTopic model...")
        # We pass pre-computed embeddings, so no embedding_model is needed here.
        # `language="english"` helps with stop words. `min_topic_size` prevents tiny topics.
        topic_model = BERTopic(language="english", min_topic_size=5)
        topic_model.fit_transform(titles, embeddings=embeddings)

        # Get the top 5 topics, excluding the outlier topic (-1)
        top_topics = topic_model.get_topic_info()[1:8] # Slicing skips topic -1

        if top_topics.empty:
            print("BERTopic did not identify any significant topics.")
            return

        print(f"Identified {len(top_topics)} topics. Generating labels with Gemini...")

        # Collect representative documents for all top topics
        grouped_docs = {
            topic_id: topic_model.get_representative_docs(topic_id)
            for topic_id in top_topics.Topic
        }

        # Generate all topic labels in a single API call
        generated_topic_objects = generate_topics(grouped_docs)

        # The service returns a list of dicts, e.g., [{'label': 'Topic 1'}, {'label': 'Topic 2'}]
        # We need to extract the 'label' from each.
        final_topics = [topic['label'] for topic in generated_topic_objects]

        print("Successfully generated topic labels:")
        for topic in final_topics:
            print(f"- {topic}")

        print("Saving topics to database and JSON file...")
        with conn.cursor() as cur:
            # Use a single timestamp for the entire batch
            batch_timestamp = datetime.now()
            # Insert new topics
            for topic in final_topics:
                cur.execute(
                    "INSERT INTO daily_topics (topic, created_at) VALUES (%s, %s)",
                    (topic, batch_timestamp)
                )

        conn.commit()

        # Save to a static JSON file for the frontend
        output_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'web', 'static', 'daily_topics.json'))
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({"topics": final_topics}, f, ensure_ascii=False, indent=2)

        print(f"Successfully saved {len(final_topics)} topics to the database and to {output_path}")

    except psycopg2.Error as e:
        print(f"Database error: {e}", file=sys.stderr)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main()
