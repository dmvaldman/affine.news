from http.server import BaseHTTPRequestHandler
import json
from urllib.parse import urlparse, parse_qs
import os
import psycopg2
from psycopg2.extras import DictCursor
from pgvector.psycopg2 import register_vector
import google.generativeai as genai
import numpy as np

SIMILARITY_THRESHOLD = 0.6  # Minimum similarity score to be included in results

def generate_summary(client: genai.GenerativeModel, search_query: str, results_by_iso: dict) -> str:
    """
    Generates a summary paragraph from article headlines using an LLM.

    Args:
        client: The configured Gemini client.
        search_query: The user's original search query.
        results_by_iso: A dictionary of search results grouped by country ISO code.

    Returns:
        A string containing the generated summary, or an empty string if an error occurs.
    """
    if not results_by_iso:
        return ""

    prompt_parts = [
        f"""
        You are an unbiased news analyst favoring no nation over another. Below are headlines from various countries for the same event, write a short paragraph summarizing the different angles and points of emphasis in the coverage. Highlight any divergence between countries. Be concise.
        If there is no divergence or it's subtle, don't mention anything. We only want to call out clear biases. Use this format:
        - [COUNTRY, COUNTRY, ..., COUNTRY] focuses on [feature1], [feature2]
        - [COUNTRY, COUNTRY, ..., COUNTRY] focuses on [feature1], [feature2]
        ...
        2-3 lines. If there is no divergence (0-1 lines), just say "No divergence in coverage."
        """,
        f"\nUSER QUERY: \"{search_query}\"\n",
        "--- HEADLINES ---"
    ]

    # Format headlines for the prompt
    for iso, data in results_by_iso.items():
        country_name = data.get('country_name', iso)
        prompt_parts.append(f"\n{country_name}:")
        for article in data['articles']:
            prompt_parts.append(f"- {article['title']}")

    prompt = "\n".join(prompt_parts)

    try:
        model = client.GenerativeModel('gemini-2.5-flash-lite')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error generating summary: {e}")
        return ""


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Parse query parameters
        query_components = parse_qs(urlparse(self.path).query)
        search_query = query_components.get('query', [None])[0]
        date_start = query_components.get('date_start', [None])[0]
        date_end = query_components.get('date_end', [None])[0]

        if not search_query or not date_start or not date_end:
            self.send_response(400)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Missing required query parameters: query, date_start, date_end'}).encode('utf-8'))
            return

        try:
            # 1. Embed the search query
            api_key = os.environ.get('GEMINI_API_KEY')
            if not api_key:
                raise ValueError("GEMINI_API_KEY not set")

            genai.configure(api_key=api_key)

            query_embedding_response = genai.embed_content(
                model="models/embedding-001",
                content=search_query,
                task_type="retrieval_query"
            )
            query_embedding = query_embedding_response['embedding']

            # 2. Query the database
            db_url = os.environ.get('DATABASE_URL')
            if not db_url:
                raise ValueError("DATABASE_URL not set")

            with psycopg2.connect(db_url) as conn:
                register_vector(conn)
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    # Fetch ISO, language, AND country name from the paper table
                    cur.execute("SELECT uuid, iso, lang, country FROM paper")
                    papers_data = {row['uuid']: {'iso': row['iso'], 'lang': row['lang'], 'country': row['country']} for row in cur.fetchall()}

                    # Use a CTE to calculate similarity once and then filter
                    cur.execute(
                        """
                        WITH articles_with_similarity AS (
                            SELECT
                                url,
                                title_translated,
                                publish_at,
                                paper_uuid,
                                1 - (title_embedding <=> %s) AS similarity
                            FROM article
                            WHERE
                                publish_at BETWEEN %s AND %s
                                AND title_embedding IS NOT NULL
                        )
                        SELECT
                            url,
                            title_translated,
                            publish_at,
                            paper_uuid,
                            similarity
                        FROM articles_with_similarity
                        WHERE similarity > %s
                        ORDER BY similarity DESC
                        LIMIT 50;
                        """,
                        (np.array(query_embedding), date_start, date_end, SIMILARITY_THRESHOLD)
                    )
                    results = cur.fetchall()

            final_response = {}

            if not results:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(final_response).encode('utf-8'))
                return

            # Format results grouped by ISO
            by_iso = {}
            for row in results:
                paper_info = papers_data.get(row['paper_uuid'], {})
                iso = paper_info.get('iso')
                if not iso:
                    continue

                if iso not in by_iso:
                    by_iso[iso] = {
                        "country_name": paper_info.get('country'),
                        "articles": []
                    }

                by_iso[iso]["articles"].append({
                    "article_url": row['url'],
                    "title": row['title_translated'],
                    "publish_at": row['publish_at'].isoformat(),
                    "lang": paper_info.get('lang'),
                    "similarity": float(row['similarity'])
                })

            # Generate summary
            summary = generate_summary(genai, search_query, by_iso)

            final_response = {
                "summary": summary,
                "articles": by_iso
            }

            # 3. Send the response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(final_response).encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))

        return
