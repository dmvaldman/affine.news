from http.server import BaseHTTPRequestHandler
import json
from urllib.parse import urlparse, parse_qs
import os
import psycopg2
from psycopg2.extras import DictCursor
from pgvector.psycopg2 import register_vector
import google.generativeai as genai
from pydantic import BaseModel
import numpy as np
import hashlib
from concurrent.futures import ThreadPoolExecutor
import random

SIMILARITY_THRESHOLD = 0.63

# --- LLM Structured Output Schemas ---
class SpectrumPoint(BaseModel):
    point_id: int
    label: str

class ArticleSpectrumMapping(BaseModel):
    article_id: int
    point_id: int

class LlmSankeyResult(BaseModel):
    spectrum_name: str
    spectrum_description: str
    spectrum_points: list[SpectrumPoint]
    mappings: list[ArticleSpectrumMapping]


def generate_sankey_data_with_llm(client: genai.GenerativeModel, articles_data: list) -> LlmSankeyResult | None:
    """
    Asks an LLM to define a single political spectrum and map articles to it.
    """
    print("\nGenerating single-dimension analysis with LLM...")

    prompt_parts = [
        "You are a political analyst creating a dataset for a visualization.",
        "Below is a numbered list of news headlines about the same topic from various international sources.",
        "Your task has three parts:",
        "1. Identify the single MOST IMPORTANT political dimension or axis of debate in these headlines. Give this spectrum a clear name and a brief description.",
        "2. Define an ordered political spectrum of 2 to 4 points for this dimension. The spectrum must span the range of viewpoints from a clear negative/opposing stance to a positive/supportive one.",
        "3. For EACH headline, map it to the most appropriate point on the spectrum you defined.",
        "Provide the final output as a single JSON object.",
        "---",
        "HEADLINES:"
    ]

    for i, article in enumerate(articles_data):
        prompt_parts.append(f"{i+1}. {article['title']} ({article['country']})")

    prompt = "\n".join(prompt_parts)

    try:
        response = client.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
                response_schema=LlmSankeyResult
            )
        )
        response_data = json.loads(response.text)
        return LlmSankeyResult(**response_data)
    except Exception as e:
        print(f"Error during LLM single-dimension analysis: {e}")
        return None


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

            articles_data = []
            with psycopg2.connect(db_url) as conn:
                register_vector(conn)
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    # Fetch paper metadata
                    cur.execute("SELECT uuid, iso, country, lang FROM paper")
                    papers_data = {row['uuid']: {'iso': row['iso'], 'country': row['country'], 'lang': row['lang']} for row in cur.fetchall()}

                    # Query articles with embeddings
                    cur.execute(
                        """
                        SELECT
                            url,
                            title_translated,
                            paper_uuid,
                            title_embedding,
                            publish_at,
                            lang,
                            1 - (title_embedding <=> %s) AS similarity
                        FROM article
                        WHERE
                            publish_at BETWEEN %s AND %s
                            AND title_embedding IS NOT NULL
                            AND 1 - (title_embedding <=> %s) > %s
                        ORDER BY similarity DESC
                        LIMIT 200;
                        """,
                        (np.array(query_embedding), date_start, date_end, np.array(query_embedding), SIMILARITY_THRESHOLD)
                    )
                    results = cur.fetchall()

                    for row in results:
                        paper_info = papers_data.get(row['paper_uuid'])
                        if paper_info:
                            articles_data.append({
                                "title": row['title_translated'],
                                "url": row['url'],
                                "iso": paper_info['iso'],
                                "country": paper_info['country'],
                                "publish_at": row['publish_at'].isoformat() if row['publish_at'] else None,
                                "lang": row['lang'] if row['lang'] else paper_info['lang'],
                                "embedding": np.array(row['title_embedding'])
                            })

            if not articles_data:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "spectrum_name": None,
                    "spectrum_description": None,
                    "spectrum_points": [],
                    "articles": {}
                }).encode('utf-8'))
                return

            print(f"Step 2 successful. Found {len(articles_data)} articles.")

            # --- Filter out countries with < 2 articles ---
            print("Filtering out countries with fewer than 2 articles...")
            articles_by_iso_temp = {}
            for article in articles_data:
                iso = article['iso']
                if iso not in articles_by_iso_temp:
                    articles_by_iso_temp[iso] = []
                articles_by_iso_temp[iso].append(article)

            filtered_articles_data = []
            for iso, articles in articles_by_iso_temp.items():
                if len(articles) >= 2:
                    filtered_articles_data.extend(articles)

            num_removed = len(articles_data) - len(filtered_articles_data)
            articles_data = filtered_articles_data
            print(f"Removed {num_removed} articles from countries with < 2 articles. {len(articles_data)} articles remaining.")

            if not articles_data:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "spectrum_name": None,
                    "spectrum_description": None,
                    "spectrum_points": [],
                    "articles": {}
                }).encode('utf-8'))
                return

            # 3. Generate spectrum analysis using LLM
            print("Step 3: Generating spectrum analysis...")
            gemini_client = genai.GenerativeModel('gemini-2.5-flash')
            analysis_result = generate_sankey_data_with_llm(gemini_client, articles_data)

            if not analysis_result:
                raise ValueError("Could not get analysis from LLM")

            print(f"Spectrum: {analysis_result.spectrum_name}")

            # 4. Format response
            print("Step 4: Formatting response...")
            mapping_dict = {m.article_id: m.point_id for m in analysis_result.mappings}

            # Group articles by ISO
            articles_by_iso = {}
            for i, article in enumerate(articles_data):
                article_id_llm = i + 1
                point_id = mapping_dict.get(article_id_llm)
                iso = article['iso']

                if iso not in articles_by_iso:
                    articles_by_iso[iso] = {
                        "country": article['country'],
                        "articles": []
                    }

                articles_by_iso[iso]["articles"].append({
                    "title": article['title'],
                    "url": article['url'],
                    "publish_at": article['publish_at'],
                    "lang": article['lang'],
                    "point_id": point_id
                })

            final_response = {
                "spectrum_name": analysis_result.spectrum_name,
                "spectrum_description": analysis_result.spectrum_description,
                "spectrum_points": [
                    {"point_id": p.point_id, "label": p.label}
                    for p in sorted(analysis_result.spectrum_points, key=lambda x: x.point_id)
                ],
                "articles": articles_by_iso
            }

            # 5. Send response with caching headers
            body = json.dumps(final_response, sort_keys=True).encode('utf-8')
            etag = '"' + hashlib.sha1(body).hexdigest() + '"'

            if self.headers.get('if-none-match') == etag:
                self.send_response(304)
                self.end_headers()
                return

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'public, max-age=14400')  # 4 hours
            self.send_header('CDN-Cache-Control', 'public, s-maxage=14400')
            self.send_header('ETag', etag)
            self.end_headers()
            self.wfile.write(body)

        except Exception as e:
            print(f"An error occurred: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))

        return
