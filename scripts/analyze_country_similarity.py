"""
Analyze country similarity from country × topic matrix.
Uses correlation on position means across topics.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from scipy.stats import pearsonr, skew, kurtosis
from scipy.cluster.hierarchy import linkage, dendrogram
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.mixture import GaussianMixture


MATRIX_FILE = Path(__file__).parent.parent / "data" / "country_topic_matrix.csv"
MIN_COMMON_TOPICS = 5


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

        if mask.sum() < MIN_COMMON_TOPICS:
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

            if len(vec1) < MIN_COMMON_TOPICS:
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
        for s in similarities[:50]:
            print(f"{s['country']:<10} {s['correlation']:>12.3f} {s['common_topics']:>8} {s['p_value']:>10.4f}")

    else:
        # Show all pairs
        pairs = []
        for i, c1 in enumerate(countries):
            for c2 in countries[i+1:]:
                vec1, vec2 = get_common_positions(c1, c2)

                if len(vec1) < MIN_COMMON_TOPICS:
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

        print(f"\nTop 50 most similar country pairs:")
        print(f"{'Country A':<10} {'Country B':<10} {'Correlation':>12} {'Topics':>8}")
        print("-" * 42)
        for p in pairs[:50]:
            print(f"{p['country_a']:<10} {p['country_b']:<10} {p['correlation']:>12.3f} {p['common_topics']:>8}")

        print(f"\nTop 50 most dissimilar country pairs:")
        print(f"{'Country A':<10} {'Country B':<10} {'Correlation':>12} {'Topics':>8}")
        print("-" * 42)
        for p in sorted(pairs, key=lambda x: x["correlation"])[:50]:
            print(f"{p['country_a']:<10} {p['country_b']:<10} {p['correlation']:>12.3f} {p['common_topics']:>8}")


def cluster_countries(df: pd.DataFrame, n_clusters: int = 5):
    """Cluster countries based on their topic positions using sparse methods"""
    print(f"\n=== COUNTRY CLUSTERING ===")

    # Method 1: Use only countries with sufficient data
    min_topics = 20  # Minimum topics required for clustering
    countries_with_data = df.count(axis=1) >= min_topics
    df_filtered = df[countries_with_data]

    if len(df_filtered) < n_clusters:
        print(f"Not enough countries with {min_topics}+ topics for clustering")
        return {}

    print(f"Clustering {len(df_filtered)} countries with {min_topics}+ topics")

    # Fill remaining NaN with per-country mean, then with overall mean
    df_filled = df_filtered.fillna(df_filtered.mean(axis=1), axis=0)
    df_filled = df_filled.fillna(df_filled.mean().mean())  # Fill any remaining NaN with overall mean

    # Check for any remaining NaN values
    if df_filled.isna().any().any():
        print(f"Warning: Still have NaN values, filling with 0")
        df_filled = df_filled.fillna(0)

    # Standardize
    scaler = StandardScaler()
    df_scaled = scaler.fit_transform(df_filled)

    # Final check for NaN in scaled data
    if np.isnan(df_scaled).any():
        print(f"Warning: NaN values in scaled data, replacing with 0")
        df_scaled = np.nan_to_num(df_scaled, nan=0.0)

    # Hierarchical clustering
    clustering = AgglomerativeClustering(n_clusters=n_clusters)
    country_clusters = clustering.fit_predict(df_scaled)

    # Group countries by cluster
    clusters = {}
    for i, country in enumerate(df_filtered.index):
        cluster_id = country_clusters[i]
        if cluster_id not in clusters:
            clusters[cluster_id] = []
        clusters[cluster_id].append(country)

    print(f"Found {len(clusters)} clusters:")
    for cluster_id, countries in clusters.items():
        print(f"  Cluster {cluster_id}: {', '.join(countries)}")

    return clusters


def robust_z_score(series):
    """Calculates the Modified Z-score, which is robust to outliers."""
    median = series.median()
    mad = (series - median).abs().median()
    if mad == 0: # Avoid division by zero
        return pd.Series(0, index=series.index)

    # The 0.6745 is a scaling factor to make MAD comparable to standard deviation
    modified_z_score = 0.6745 * (series - median) / mad
    return modified_z_score


def analyze_topic_contention(df: pd.DataFrame, top_n: int = 10, spread_percentile_range: tuple = (0.1, 0.9)):
    """
    Calculates a "Contention Profile" for each topic to identify different
    types of polarization, focusing on true bimodal splits and outlier impact.
    """
    print(f"\n=== TOPIC CONTENTION ANALYSIS ===")

    min_countries = 15  # Minimum countries for a robust analysis
    topics_with_data = df.count(axis=0) >= min_countries
    df_filtered = df.loc[:, topics_with_data]
    print(f"Analyzing {len(df_filtered.columns)} topics with {min_countries}+ countries")

    profiles = {}
    for topic in df_filtered.columns:
        topic_data = df_filtered[topic].dropna()

        # Bimodality check with Gaussian Mixture Model
        data_reshaped = topic_data.values.reshape(-1, 1)
        gmm1 = GaussianMixture(n_components=1, n_init=10, random_state=42).fit(data_reshaped)
        gmm2 = GaussianMixture(n_components=2, n_init=10, random_state=42).fit(data_reshaped)
        bic1 = gmm1.bic(data_reshaped)
        bic2 = gmm2.bic(data_reshaped)

        bimodal_likelihood = bic1 - bic2
        means = sorted(gmm2.means_.flatten().tolist())

        # New: Check for true polarization (clusters on opposite sides of 2.5)
        polarization_score = 0
        if bimodal_likelihood > 10 and means[0] < 2.5 and means[1] > 2.5:
            polarization_score = bimodal_likelihood

        # Robust spread metric: Configurable percentile range
        q1 = topic_data.quantile(spread_percentile_range[0])
        q3 = topic_data.quantile(spread_percentile_range[1])
        spread_range = q3 - q1

        # Analyze skewness and outlier impact using robust z-scores
        z_scores = np.abs(robust_z_score(topic_data))
        outliers = topic_data[z_scores > 2.0]
        data_no_outliers = topic_data[z_scores <= 2.0]
        skew_full = topic_data.skew()
        skew_no_outliers = data_no_outliers.skew() if len(data_no_outliers) > 1 else 0

        profiles[topic] = {
            "spread_range": spread_range,
            "skewness": abs(skew_full),
            "polarization_score": polarization_score,
            "cluster_means": means if polarization_score > 0 else None,
            "skew_impact": abs(skew_full) - abs(skew_no_outliers),
            "skew_outliers": outliers.to_dict()
        }

    # Rank and display topics

    # 1. Most Polarized (True Bimodal)
    print("\n--- Most Polarized Topics (Clusters straddle 2.5) ---")
    sorted_bimodal = sorted(profiles.items(), key=lambda x: x[1]['polarization_score'], reverse=True)
    for i, (topic, data) in enumerate(sorted_bimodal[:top_n]):
        if data['polarization_score'] == 0: continue
        print(f"  {i+1:2d}. {topic:<40} (Score: {data['polarization_score']:.2f})")
        if data['cluster_means']:
            print(f"      Clusters at: {data['cluster_means'][0]:.2f} and {data['cluster_means'][1]:.2f}")

            # Show countries in each cluster
            topic_data = df[topic].dropna()
            cluster1_countries = topic_data[topic_data <= 2.5].sort_values(ascending=False)
            cluster2_countries = topic_data[topic_data > 2.5].sort_values(ascending=False)

            cluster1_str = ', '.join([f"{c}: {s:.2f}" for c, s in cluster1_countries.head(3).items()])
            cluster2_str = ', '.join([f"{c}: {s:.2f}" for c, s in cluster2_countries.head(3).items()])
            print(f"      Cluster 1 (≤2.5): {cluster1_str}")
            print(f"      Cluster 2 (>2.5): {cluster2_str}")
            print()

    # 2. Widest Spread (Robust - Configurable Percentile Range)
    percentile_range_name = f"{int(spread_percentile_range[0]*100)}-{int(spread_percentile_range[1]*100)}%"
    print(f"\n--- Widest Spread Topics (Robust - {percentile_range_name} Range) ---")
    sorted_spread = sorted(profiles.items(), key=lambda x: x[1]['spread_range'], reverse=True)
    for i, (topic, data) in enumerate(sorted_spread[:top_n]):
        print(f"  {i+1:2d}. {topic:<40} (Range: {data['spread_range']:.3f})")

        # Show top 2 countries bookending the spread
        topic_data = df[topic].dropna().sort_values(ascending=False)
        top_2 = topic_data.head(2)
        bottom_2 = topic_data.tail(2)

        top_str = ', '.join([f"{c}: {s:.2f}" for c, s in top_2.items()])
        bottom_str = ', '.join([f"{c}: {s:.2f}" for c, s in bottom_2.items()])
        print(f"      Top 2: {top_str}")
        print(f"      Bottom 2: {bottom_str}")
        print()

    return profiles


def find_outlier_countries(df: pd.DataFrame, threshold: float = 2.0, min_countries_filter: int = 1, max_countries_filter: int = 5):
    """Find topics where few countries care significantly more and show their impact."""
    print(f"\n=== COUNTRY OUTLIERS PER TOPIC (IMPACT ANALYSIS) ===")

    outliers_impact = {}
    min_data_points = 15  # Minimum countries needed for outlier detection

    for topic in df.columns:
        topic_data = df[topic].dropna()
        if len(topic_data) < min_data_points:
            continue

        z_scores = np.abs(robust_z_score(topic_data))
        outlier_countries = topic_data[z_scores > threshold]

        if min_countries_filter <= len(outlier_countries) <= max_countries_filter:
            data_no_outliers = topic_data[z_scores <= threshold]

            if len(data_no_outliers) > 1:
                var_full = topic_data.var()
                var_no_outliers = data_no_outliers.var()
                variance_impact = var_full - var_no_outliers

                outliers_impact[topic] = {
                    'countries': outlier_countries.to_dict(),
                    'variance_impact': variance_impact,
                    'mean_full': topic_data.mean(),
                    'mean_no_outliers': data_no_outliers.mean(),
                    'total_countries': len(topic_data)
                }

    # Sort by variance impact
    sorted_impact = sorted(outliers_impact.items(), key=lambda x: x[1]['variance_impact'], reverse=True)

    print(f"Topics with {min_countries_filter}-{max_countries_filter} outlier countries (min {min_data_points} countries):")
    for i, (topic, data) in enumerate(sorted_impact[:15]):
        outlier_str = ', '.join([f"{c}: {s:.2f}" for c, s in data['countries'].items()])
        print(f"  {i+1:2d}. {topic:<40}")
        print(f"      Outliers: {outlier_str}")
        print(f"      Mean without outliers: {data['mean_no_outliers']:.2f}")
        print()

    return outliers_impact


def find_country_extreme_positions(df: pd.DataFrame, country: str, top_n: int = 15):
    """Find topics where a specific country has the most extreme positions"""
    print(f"\n=== EXTREME POSITIONS FOR {country.upper()} ===")

    if country not in df.index:
        print(f"Country {country} not found in data")
        return {}

    country_data = df.loc[country].dropna()
    if len(country_data) == 0:
        print(f"No data found for {country}")
        return {}

    # Calculate how extreme each position is relative to other countries
    extreme_scores = {}

    for topic in country_data.index:
        topic_data = df[topic].dropna()
        if len(topic_data) < 5:  # Need enough countries for comparison
            continue

        country_score = country_data[topic]

        # Calculate robust z-score for this country's position
        robust_z = robust_z_score(topic_data)
        country_z_score = abs(robust_z[country]) if country in robust_z.index else 0

        # Calculate distance from median
        median = topic_data.median()
        distance_from_median = abs(country_score - median)

        # Calculate percentile rank (how extreme relative to others)
        percentile_rank = (topic_data < country_score).sum() / len(topic_data)
        percentile_extremity = max(percentile_rank, 1 - percentile_rank)  # Distance from 0.5

        extreme_scores[topic] = {
            'score': country_score,
            'robust_z_score': country_z_score,
            'distance_from_median': distance_from_median,
            'percentile_extremity': percentile_extremity,
            'median': median,
            'total_countries': len(topic_data)
        }

    # Sort by different extreme measures
    print(f"\nMost extreme positions by robust z-score:")
    sorted_by_z = sorted(extreme_scores.items(), key=lambda x: x[1]['robust_z_score'], reverse=True)
    for i, (topic, data) in enumerate(sorted_by_z[:top_n]):
        print(f"  {i+1:2d}. {topic:<40} (Score: {data['score']:.2f}, Z: {data['robust_z_score']:.2f})")

    print(f"\nMost extreme positions by distance from median:")
    sorted_by_distance = sorted(extreme_scores.items(), key=lambda x: x[1]['distance_from_median'], reverse=True)
    for i, (topic, data) in enumerate(sorted_by_distance[:top_n]):
        print(f"  {i+1:2d}. {topic:<40} (Score: {data['score']:.2f}, Median: {data['median']:.2f}, Distance: {data['distance_from_median']:.2f})")

    print(f"\nMost extreme positions by percentile rank:")
    sorted_by_percentile = sorted(extreme_scores.items(), key=lambda x: x[1]['percentile_extremity'], reverse=True)
    for i, (topic, data) in enumerate(sorted_by_percentile[:top_n]):
        percentile_rank = (topic_data < country_data[topic]).sum() / len(topic_data) if topic in topic_data.index else 0
        direction = "pro" if country_data[topic] > 2.5 else "anti"
        print(f"  {i+1:2d}. {topic:<40} (Score: {data['score']:.2f}, {direction}, Percentile: {percentile_rank:.1%})")

    return extreme_scores


def analyze_matrix(df: pd.DataFrame, spread_percentile_range: tuple = (0.25, 0.75)):
    """Run comprehensive analysis"""
    print(f"Matrix shape: {df.shape[0]} countries × {df.shape[1]} topics")

    # Basic stats
    print(f"\n=== BASIC STATISTICS ===")
    print(f"Countries with most topics: {df.count(axis=1).sort_values(ascending=False).head(5).to_dict()}")
    print(f"Topics with most countries: {df.count(axis=0).sort_values(ascending=False).head(5).to_dict()}")

    # Run analyses
    clusters = cluster_countries(df, n_clusters=5)
    contention = analyze_topic_contention(df, spread_percentile_range=spread_percentile_range)
    outliers = find_outlier_countries(df)

    return {
        'clusters': clusters,
        'contention': contention,
        'outliers': outliers
    }


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Analyze country similarity')
    parser.add_argument('--country', type=str, help='ISO code of focal country')
    parser.add_argument('--analysis', action='store_true', help='Run comprehensive analysis')
    parser.add_argument('--extreme', action='store_true', help='Find extreme positions for a country')
    parser.add_argument('--clusters', type=int, default=5, help='Number of clusters for clustering analysis')
    parser.add_argument('--spread-range', type=float, nargs=2, default=[0.1, 0.9],
                       help='Percentile range for spread analysis (default: 0.25 0.75 for IQR)')
    args = parser.parse_args()

    df = load_matrix()

    if df.empty:
        print("No matrix data found. Run build_country_topic_matrix.py first.")
        exit(1)

    if args.analysis:
        spread_range = tuple(args.spread_range)
        analyze_matrix(df, spread_percentile_range=spread_range)
    elif args.extreme:
        if not args.country:
            print("Error: --extreme requires --country to be specified")
            exit(1)
        find_country_extreme_positions(df, args.country)
    else:
        compute_similarity(df, args.country)

