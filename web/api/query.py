from http.server import BaseHTTPRequestHandler
import json
from urllib.parse import urlparse, parse_qs
import os
import psycopg  # type: ignore
from psycopg.rows import dict_row  # type: ignore
import google.generativeai as genai
from pydantic import BaseModel
import hashlib

SIMILARITY_THRESHOLD = 0.63  # Minimum similarity score to be included in results

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

    class Slant(BaseModel):
        countries: list[str]
        label: str

    prompt_parts = [
        f"""
        You're an unbiased global news analyst.
        Below are news headlines from various countries for the same event.
        Your are to extract critical bias across countries if present.
        Respond with groups of countries (use their ISO code) and a 2-8 word concise label indicating the bias.
        e.g. ["USA", "GBR", "CAN"], "Downplay incident". ["CHI", "RUS"], "Highlight Israel aggression".
        We're only looking for obvious biases, not subtle differences. If subtle ignore.
        If a country's reporting is mostly neutral, ignore. Don't mention that they have "neutral" reporting or similar as a label (this is done automatically).
        It's not enough for one article to simply mention a different aspect of a story. It must show a clear bias. E.g. pushing one narrative vs its opposite.
        Not all countries need be included, in fact, many won't be.
        0-4 groups of countries/label total. 4 should be reserved for cases of extreme controversy and bias.
        If little divergence overall respond [], ''.
        """,
        "--- HEADLINES ---"
    ]

    # Format headlines for the prompt
    for iso, data in results_by_iso.items():
        country_name = data.get('country_name', iso)

        # Only try to form summary opinion if there are enough articles
        if len(data['articles']) < 3:
            continue

        prompt_parts.append(f"\n{country_name}:")
        for article in data['articles']:
            prompt_parts.append(f"- {article['title']}")

    prompt = "\n".join(prompt_parts)

    try:
        model = client.GenerativeModel('gemini-2.5-flash-lite')
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
                response_schema=list[Slant]
            )
        )
        return json.loads(response.text)
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
            print("Step 1: Embedding the search query...")
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
            print("Step 1 successful.")

            # 2. Query the database
            print("Step 2: Querying the database...")
            db_url = os.environ.get('DATABASE_URL')
            if not db_url:
                raise ValueError("DATABASE_URL not set")

            # Convert embedding list to PostgreSQL vector string format
            embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'

            with psycopg.connect(db_url) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
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
                                1 - (title_embedding <=> %s::vector) AS similarity
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
                        LIMIT 200;
                        """,
                        (embedding_str, date_start, date_end, SIMILARITY_THRESHOLD)
                    )
                    results = cur.fetchall()
            print(f"Step 2 successful. Found {len(results)} articles.")

            final_response = {}

            if not results:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"summary": [], "articles": {}}).encode('utf-8'))
                return

            # Format results grouped by ISO
            print("Step 3: Formatting results and generating summary...")
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
            print("Step 3 successful.")

            # Convert to unified format (spectrum fields are null for this endpoint)
            final_response = {
                "spectrum_name": None,
                "spectrum_description": None,
                "spectrum_points": [],
                "summary": summary,  # Legacy field, kept for backwards compatibility
                "articles": by_iso
            }

            # 4. Send the response with caching headers
            body = json.dumps(final_response, sort_keys=True).encode('utf-8')
            etag = '"' + hashlib.sha1(body).hexdigest() + '"'

            if self.headers.get('if-none-match') == etag:
                self.send_response(304)
                self.end_headers()
                return

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'public, max-age=14400') # 4 hours browser cache
            self.send_header('CDN-Cache-Control', 'public, s-maxage=14400') # 4 hours edge cache
            self.send_header('ETag', etag)
            self.end_headers()
            self.wfile.write(body)

        except Exception as e:
            print(f"An error occurred in the main handler: {e}") # Log the full error
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))

        return
