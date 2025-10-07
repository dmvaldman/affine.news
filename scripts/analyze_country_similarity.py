"""
Analyze country similarity from country × topic matrix.
Uses correlation on position means across topics.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from scipy.stats import pearsonr


MATRIX_FILE = Path(__file__).parent.parent / "data" / "country_topic_matrix.csv"


def load_matrix() -> pd.DataFrame:
    """Load country × topic matrix"""
    if not MATRIX_FILE.exists():
        print(f"Matrix file not found: {MATRIX_FILE}")
        return pd.DataFrame()

    return pd.read_csv(MATRIX_FILE, index_col=0)


def compute_similarity(df: pd.DataFrame, focal_country: str = None):
    """
    Compute country similarity based on position correlation.

    Args:
        df: Country × topic DataFrame
        focal_country: If provided, show similarity only for this country
    """
    countries = df.index.tolist()

    if len(countries) < 2:
        print("Need at least 2 countries to compute similarity")
        return

    print(f"Analyzing {len(countries)} countries across {df.shape[1]} topics...")

    # Get vectors for two countries, aligned on common topics (non-NaN)
    def get_common_positions(c1: str, c2: str) -> tuple[np.ndarray, np.ndarray]:
        """Get position vectors for common topics"""
        vec1 = df.loc[c1]
        vec2 = df.loc[c2]

        # Find topics where both have values
        mask = ~(vec1.isna() | vec2.isna())

        if mask.sum() < 2:
            return np.array([]), np.array([])

        return vec1[mask].values, vec2[mask].values

    if focal_country:
        if focal_country not in countries:
            print(f"Country {focal_country} not found")
            return

        similarities = []
        for country in countries:
            if country == focal_country:
                continue

            vec1, vec2 = get_common_positions(focal_country, country)

            if len(vec1) < 2:
                continue

            # Compute Pearson correlation
            corr, p_value = pearsonr(vec1, vec2)

            similarities.append({
                "country": country,
                "correlation": corr,
                "common_topics": len(vec1),
                "p_value": p_value
            })

        similarities.sort(key=lambda x: x["correlation"], reverse=True)

        print(f"\nCountries most similar to {focal_country}:")
        print(f"{'Country':<10} {'Correlation':>12} {'Topics':>8} {'P-value':>10}")
        print("-" * 42)
        for s in similarities[:20]:
            print(f"{s['country']:<10} {s['correlation']:>12.3f} {s['common_topics']:>8} {s['p_value']:>10.4f}")

    else:
        # Show all pairs
        pairs = []
        for i, c1 in enumerate(countries):
            for c2 in countries[i+1:]:
                vec1, vec2 = get_common_positions(c1, c2)

                if len(vec1) < 2:
                    continue

                corr, p_value = pearsonr(vec1, vec2)

                pairs.append({
                    "country_a": c1,
                    "country_b": c2,
                    "correlation": corr,
                    "common_topics": len(vec1),
                    "p_value": p_value
                })

        pairs.sort(key=lambda x: x["correlation"], reverse=True)

        print(f"\nTop 20 most similar country pairs:")
        print(f"{'Country A':<10} {'Country B':<10} {'Correlation':>12} {'Topics':>8}")
        print("-" * 42)
        for p in pairs[:20]:
            print(f"{p['country_a']:<10} {p['country_b']:<10} {p['correlation']:>12.3f} {p['common_topics']:>8}")

        print(f"\nTop 20 most dissimilar country pairs:")
        print(f"{'Country A':<10} {'Country B':<10} {'Correlation':>12} {'Topics':>8}")
        print("-" * 42)
        for p in sorted(pairs, key=lambda x: x["correlation"])[:20]:
            print(f"{p['country_a']:<10} {p['country_b']:<10} {p['correlation']:>12.3f} {p['common_topics']:>8}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Analyze country similarity')
    parser.add_argument('--country', type=str, help='ISO code of focal country')
    args = parser.parse_args()

    df = load_matrix()

    if df.empty:
        print("No matrix data found. Run build_country_topic_matrix.py first.")
        exit(1)

    compute_similarity(df, args.country)

