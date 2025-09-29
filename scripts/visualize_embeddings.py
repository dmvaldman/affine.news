import os
import sys
import psycopg2
from psycopg2.extras import DictCursor
from pgvector.psycopg2 import register_vector
import google.generativeai as genai
from dotenv import load_dotenv
import numpy as np
from datetime import datetime, timedelta
import json
from pydantic import BaseModel
import plotly.graph_objects as go

# --- LLM Structured Output Schemas ---
class SpectrumPoint(BaseModel):
    point_id: int
    label: str # e.g., "Strongly Opposes"

class ArticleSpectrumMapping(BaseModel):
    article_id: int
    point_id: int

class LlmSankeyResult(BaseModel):
    spectrum_name: str
    spectrum_description: str
    spectrum_points: list[SpectrumPoint]
    mappings: list[ArticleSpectrumMapping]


# --- Configuration ---
# SEARCH_QUERY = "Gaza Israel genocide"
# SEARCH_QUERY = "James Comey Indicted"
# SEARCH_QUERY = "Iran Russia nuclear deal"
# SEARCH_QUERY = "Recognizition for a Palestinian state"
SEARCH_QUERY = "Moldova election interference"
SIMILARITY_THRESHOLD = 0.65
DATE_START = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
DATE_END = datetime.now().strftime('%Y-%m-%d')

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


def main():
    """
    Fetches articles, uses an LLM to categorize them on a political spectrum,
    and visualizes it with matplotlib.
    """
    load_dotenv()
    print(f"--- Visualizing embeddings for query: '{SEARCH_QUERY}' ---")

    try:
        # 1. Embed the search query
        print("Step 1: Embedding the search query...")
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set")
        genai.configure(api_key=api_key)

        query_embedding_response = genai.embed_content(
            model="models/embedding-001",
            content=SEARCH_QUERY,
            task_type="retrieval_query"
        )
        query_embedding = query_embedding_response['embedding']
        print("Step 1 successful.")

        # 2. Query the database
        print("Step 2: Querying the database for similar articles...")
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            raise ValueError("DATABASE_URL not set")

        articles_data = []
        with psycopg2.connect(db_url) as conn:
            register_vector(conn)
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute("SELECT uuid, iso, country FROM paper")
                papers_data = {row['uuid']: {'iso': row['iso'], 'country': row['country']} for row in cur.fetchall()}

                cur.execute(
                    """
                    SELECT
                        url,
                        title_translated,
                        paper_uuid,
                        title_embedding,
                        1 - (title_embedding <=> %s) AS similarity
                    FROM article
                    WHERE
                        publish_at BETWEEN %s AND %s
                        AND title_embedding IS NOT NULL
                        AND 1 - (title_embedding <=> %s) > %s
                    ORDER BY similarity DESC
                    LIMIT 200;
                    """,
                    (np.array(query_embedding), DATE_START, DATE_END, np.array(query_embedding), SIMILARITY_THRESHOLD)
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
                            "embedding": np.array(row['title_embedding'])
                        })

        if not articles_data:
            print("No articles found matching the criteria. Exiting.")
            return

        print(f"Step 2 successful. Found {len(articles_data)} articles.")

        # --- Filter out single-article countries ---
        print("Filtering out countries with only one article...")
        articles_by_iso = {}
        for article in articles_data:
            iso = article['iso']
            if iso not in articles_by_iso:
                articles_by_iso[iso] = []
            articles_by_iso[iso].append(article)

        filtered_articles_data = []
        for iso, articles in articles_by_iso.items():
            if len(articles) > 1:
                filtered_articles_data.extend(articles)

        num_removed = len(articles_data) - len(filtered_articles_data)
        articles_data = filtered_articles_data # Overwrite with filtered list

        print(f"Removed {num_removed} articles from single-article countries. {len(articles_data)} articles remaining.")
        # --- End filtering ---

        if not articles_data:
            print("No countries with multiple articles found. Exiting.")
            return

        # 3. Generate single-dimension analysis using LLM
        gemini_client = genai.GenerativeModel('gemini-2.5-flash')
        analysis_result = generate_sankey_data_with_llm(gemini_client, articles_data)

        if not analysis_result:
            print("Could not get analysis from LLM. Exiting.")
            sys.exit(1)

        print("\n--- LLM-Generated Spectrum ---")
        print(f"Spectrum: {analysis_result.spectrum_name}")
        print(f"  Description: {analysis_result.spectrum_description}")
        spectrum_map = {p.point_id: p for p in analysis_result.spectrum_points}
        for point_id, point in spectrum_map.items():
            print(f"    - Point {point_id}: {point.label}")

        # 4. Prepare and display the Sankey chart
        print("\n--- Preparing data for Sankey chart ---")

        all_countries = sorted(list(set(a['country'] for a in articles_data)))
        spectrum_labels = [p.label for p in sorted(analysis_result.spectrum_points, key=lambda x: x.point_id)]
        all_labels = all_countries + spectrum_labels

        # Create a dictionary to count links
        link_counts = {}
        mapping_dict = {m.article_id: m.point_id for m in analysis_result.mappings}

        for i, article in enumerate(articles_data):
            article_id_llm = i + 1
            country = article['country']

            point_id = mapping_dict.get(article_id_llm)
            if point_id is not None and point_id in spectrum_map:
                country_index = all_countries.index(country)
                point_label = spectrum_map[point_id].label
                point_index = spectrum_labels.index(point_label) + len(all_countries)
                link_key = (country_index, point_index)
                link_counts[link_key] = link_counts.get(link_key, 0) + 1

        # Create links from counts
        source_indices, target_indices, values = [], [], []
        for (source, target), value in link_counts.items():
            source_indices.append(source)
            target_indices.append(target)
            values.append(value)

        # Create and display the Sankey chart
        fig = go.Figure(data=[go.Sankey(
            node=dict(
                pad=15,
                thickness=20,
                line=dict(color="black", width=0.5),
                label=all_labels,
            ),
            link=dict(
                source=source_indices,
                target=target_indices,
                value=values
            ))])

        fig.update_layout(
            title_text=f"'{SEARCH_QUERY}':<br>Dimension: {analysis_result.spectrum_name}",
            font_size=12
        )
        print(f"Displaying Sankey chart for '{analysis_result.spectrum_name}'...")
        fig.show()


    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
