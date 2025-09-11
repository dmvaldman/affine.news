from bs4 import BeautifulSoup
from crawler.services.date_extractor import extract_date_from_node

def extract_publish_date(html_snippet):
    """
    Wrapper to test the extract_date_from_node function.
    It parses the HTML snippet and passes the relevant tag to the extractor.
    """
    soup = BeautifulSoup(html_snippet, 'lxml')
    # Correctly select the actual tag from the snippet, not the `<html>` wrapper.
    tag = soup.body.find()

    date_obj = extract_date_from_node(tag)
    if date_obj:
        return date_obj.strftime('%d-%m-%Y')
    return None

def run_tests():
    # We'll assume "today" is 2025-09-11 for consistent testing
    TODAY = "11-09-2025"
    YESTERDAY = "10-09-2025"

    TEST_CASES = [
        {"html": '<p class="article-item__date">10 Sep</p>', "expected": "10-09-2025"},
        {"html": '<span data-testid="card-metadata-lastupdated" class="sc-1907e52a-1 jxhyuW">13 hrs ago</span>', "expected": TODAY},
        # Corrected: the 'datetime' attribute is the source of truth and should be parsed correctly now.
        {"html": '<time class="StoryDate__StyledTime-sc-1kanv61-0 fLnCAB text-gmr-5" datetime="2025-09-09T21:00:07Z">Yesterday</time>', "expected": "09-09-2025"},
        {"html": '<time class="timeStamp" datetime="2025-09-11T01:05:49.312Z">23 minutes ago</time>', "expected": TODAY},
        {"html": '<time class="timeStamp" datetime="2025-09-10T08:00:00.334Z">September 10</time>', "expected": YESTERDAY},
        {"html": '<time class="DateDisplay" datetime="2025-09-10T09:51:17.860Z" data-tb-date="">02:51</time>', "expected": YESTERDAY},
        {"html": '<time class="cwWSWx" datetime="2025-09-10T15:07:00+03:00">15:07</time>', "expected": YESTERDAY},
        {"html": '<time class="com-date --fourxs" datetime="10 de septiembre de 2025">10 de septiembre de 2025</time>', "expected": "10-09-2025"},
        {"html": '<span class="story-item__date-time">10/09/2025</span>', "expected": "10-09-2025"},
        {"html": '<span class="timestamp--time  timeago" title="10 Sep, 2025 11:04pm">about 7 hours ago</span>', "expected": "10-09-2025"},
        {"html": '<span class="post-date grey-light3">TODAY - 10:31 PM</span>', "expected": TODAY},
        {"html": '<span class="post-date grey-light3">YESTERDAY - 11:07 PM</span>', "expected": YESTERDAY},
        {"html": '<div class="ds-teaser-footer__notes">2025-09-09 • Världen</div>', "expected": "09-09-2025"},
        {"html": '<span data-testid="timestamp-label" class="timestamp-label">10.9. 23:09</span>', "expected": "10-09-2025"},
        {"html": '<div itemprop="datePublished" content="2025-09-10T15:30:00+03:00" class="article__publish-date">10. september 2025, 15:30</div>', "expected": "10-09-2025"},
        {"html": '<time data-timeago="{&quot;datetime&quot;:&quot;2025-09-10T21:40:00.000Z&quot;}" datetime="2025-09-11T00:40:00+03:00" title="11.09.2025, 00:40">11.09.2025, 00:40</time>', "expected": TODAY},
        {"html": '<span class="date metaFont svelte-itueop">01:45</span>', "expected": TODAY},
        {"html": '<span class="date metaFont svelte-itueop">10 sept. 2025</span>', "expected": "10-09-2025"},
        {"html": '<time data-timeago="{&quot;datetime&quot;:&quot;2025-09-10T11:43:00.000Z&quot;}" datetime="2025-09-10T14:43:00+03:00" title="10.09.2025, 14:43">10.09.2025, 14:43</time>', "expected": YESTERDAY},
        # Corrected: the datetime attribute is the source of truth.
        {"html": '<time datetime="2025-09-11T02:57:52+02:00">10.09.2025</time>', "expected": TODAY},
        {"html": '<time datetime="2025-09-11T01:55:00+02:00">pre 1 sat</time>', "expected": TODAY}
    ]

    print("--- Running Date Extraction Tests ---\n")
    passed_count = 0
    for i, test in enumerate(TEST_CASES):
        result = extract_publish_date(test["html"])
        if result == test["expected"]:
            print(f"PASS: Test {i+1}")
            passed_count += 1
        else:
            print(f"FAIL: Test {i+1}")
            print(f"  Input:    {test['html']}")
            print(f"  Expected: {test['expected']}")
            print(f"  Got:      {result}")
            print("-" * 20)

    print(f"\n--- Summary ---")
    print(f"{passed_count} / {len(TEST_CASES)} tests passed.")

if __name__ == '__main__':
    run_tests()
