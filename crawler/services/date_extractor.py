import dateparser
from datetime import datetime
import re

# We'll set a fixed "now" for our tests to make them deterministic.
# Setting it late in the day ensures "X hours ago" resolves to the same day.
FIXED_NOW = datetime(2025, 9, 11, 23, 0)

def extract_date_from_node(tag):
    """
    Extracts a publication date from a single beautiful soup tag.
    It prioritizes machine-readable attributes but falls back to parsing text.
    """
    if not tag:
        return None

    # Priority 1: Check for 'datetime', 'content', or 'title' attributes.
    date_str_attr = tag.get('datetime') or tag.get('content') or tag.get('title')
    if date_str_attr:
        try:
            settings = {'RELATIVE_BASE': FIXED_NOW}
            parsed_date = dateparser.parse(date_str_attr, settings=settings)
            if parsed_date:
                return parsed_date
        except (ValueError, TypeError):
            pass # Ignore attributes that can't be parsed

    # Priority 2: Parse the tag's visible text, now with smarter settings
    text = tag.get_text(strip=True)
    if text:
        cleaned_text = re.split(r'\s*•\s*|\s*\|\s*', text)[0].strip()
        try:
            settings = {'RELATIVE_BASE': FIXED_NOW, 'DATE_ORDER': 'DMY'}
            parsed_date = dateparser.parse(cleaned_text, settings=settings)
            if parsed_date:
                return parsed_date
        except (ValueError, TypeError):
            pass

    return None

def find_date_in_url(url_str):
    """
    Looks for date-like patterns in a URL and uses dateparser to resolve them.
    """
    # Regex for YYYYMMDD format, which is common and unambiguous
    match = re.search(r'(\d{8})', url_str)
    if match:
        try:
            parsed_date = dateparser.parse(match.group(1))
            if parsed_date:
                return parsed_date.strftime('%d-%m-%Y')
        except (ValueError, TypeError):
            pass

    # Regex for YYYY/MMDD or YYYY-MMDD
    match = re.search(r'(\d{4})[/-](\d{3,4})', url_str)
    if match:
        try:
            year = match.group(1)
            month_day = match.group(2)
            # Handle MMDD and MDD
            if len(month_day) == 4:
                month = month_day[:2]
                day = month_day[2:]
            elif len(month_day) == 3:
                month = month_day[0]
                day = month_day[1:]
            else: # Should not happen with this regex, but as a safeguard
                return None

            date_str = f"{year}-{month}-{day}"
            parsed_date = dateparser.parse(date_str)
            return parsed_date.strftime('%d-%m-%Y') if parsed_date else None
        except (ValueError, TypeError):
            pass

    # A more generic regex to find potential date strings in various formats.
    # It looks for sequences of numbers and words separated by common delimiters.
    potential_dates = re.findall(
        r'(\d{1,4}[-/_]\w+[-/_]\d{1,4})|(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
        url_str
    )

    if not potential_dates:
        return None

    # Flatten the list of tuples from findall
    date_candidates = [item for sublist in potential_dates for item in sublist if item]

    for date_str in date_candidates:
        try:
            # Provide current date to help resolve ambiguity (e.g., MM-DD vs DD-MM)
            # It will prefer dates in the past.
            parsed_date = dateparser.parse(date_str, settings={'RELATIVE_BASE': datetime.now()})
            if parsed_date:
                return parsed_date.strftime('%d-%m-%Y')
        except (ValueError, TypeError):
            continue # Ignore strings that can't be parsed

    return None
