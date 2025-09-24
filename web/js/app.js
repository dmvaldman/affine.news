const searchButtonEl = document.getElementById("submitQuery");
const searchBarEl = document.getElementById("search");
const searchResultsEl = document.getElementById("searchResults");
const topicsContainerEl = document.getElementById("topicsContainer");
const summaryEl = document.getElementById("summary");
const legendEl = document.getElementById("legend");

const url_base = "/api/";

let map; // Will be initialized after fetching paper data
let origMapData = {}; // Holds the base state of the map for the current date range
let scrapedISOs = new Set(); // Accumulates all countries we know we scrape
let hasSearchedOnce = false;

async function loadDailyTopics() {
    try {
        const blobUrl = `https://nssyc9tsuo9crae6.public.blob.vercel-storage.com/daily_topics.json`;
        const response = await fetch(blobUrl);
        if (!response.ok) {
            console.error("Could not load daily topics.");
            return;
        }
        const data = await response.json();
        const topics = data.topics;

        if (topics && topics.length > 0) {
            // topicsContainerEl.innerHTML = '<span>Trending:</span>';
            topics.forEach(topic => {
                const topicEl = document.createElement('button');
                topicEl.classList.add('topic-button');
                topicEl.textContent = topic;
                topicEl.onclick = () => {
                    searchBarEl.value = topic;
                    search(); // Trigger a search with the topic
                };
                topicsContainerEl.appendChild(topicEl);
            });
        }
    } catch (error) {
        console.error('Failed to fetch or process daily topics:', error);
    }
}

async function updateMapForDateRange(date_start, date_end) {
    try {
        const url = new URL('/api/papers', window.location.origin);
        url.searchParams.append('date_start', date_start);
        url.searchParams.append('date_end', date_end);

        const response = await fetch(url);
        const papersByCountry = await response.json();

        // Add newly found countries to our master set of scraped countries
        Object.keys(papersByCountry).forEach(iso => scrapedISOs.add(iso));

        const mapElement = document.getElementById('map');
        mapElement.innerHTML = ''; // Clear the map container

        initializeMap(papersByCountry);
    } catch (error) {
        console.error('Failed to fetch paper data:', error);
        initializeMap({}); // Initialize map even if data fetch fails
    }
}


function initializeMap(papersByCountry) {
    const allCountries = Datamap.prototype.worldTopo.objects.world.geometries
        .map(g => g.id)
        .filter(id => id !== '-99');

    allCountries.forEach(countryIso => {
        if (papersByCountry[countryIso] && papersByCountry[countryIso].length > 0) {
            // Initially, countries with articles are white ("scraped, no articles for a query")
            origMapData[countryIso] = { fillKey: 'NO_ARTICLES' };
        } else {
            // All others get the default transparent fill ("not scraped")
            origMapData[countryIso] = { fillKey: 'defaultFill' };
        }
    });

    map = new Datamap({
        element: document.getElementById('map'),
        projection: 'mercator',
        fills: {
            defaultFill: 'rgba(0,0,0,0)', // Not Scraped (Transparent)
            yellow: '#F5D442',
            blue: '#6EA7F2',
            red: '#E86E6E',
            green: '#68C67C',
            NO_BIAS: '#A9A9A9',      // Has articles, no bias group
            NO_ARTICLES: '#FFFFFF',    // Scraped, but 0 articles for query
        },
        data: { ...origMapData },
        responsive: true,
        height: null,
        width: null,
        done: function(datamap) {
            datamap.svg.selectAll('.datamaps-subunit').on('click', function(geography) {
                const countryId = geography.id;
                const targetElement = document.getElementById(countryId);

                if (targetElement) {
                    targetElement.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });

                    targetElement.parentElement.classList.add('highlight');
                    setTimeout(() => {
                        targetElement.parentElement.classList.remove('highlight');
                    }, 1000);
                }
            });
        },
        geographyConfig: {
            highlightOnHover: true,
            highlightFillColor: 'rgba(2, 56, 111, 0.8)',
            borderColor: '#666',
            borderWidth: 0.5,
            highlightBorderColor: 'rgba(0, 0, 0, 0.4)',
            highlightBorderWidth: 1,
            popupTemplate: function(geography, data) {
                // Don't show popups on mobile devices
                if (window.innerWidth < 768) {
                    return null;
                }
                let urls = papersByCountry[geography.id];
                let hoverinfo = `<div class="hoverinfo"><strong>${geography.properties.name}</strong>`;
                if (urls && urls.length > 0) {
                    hoverinfo += '<ul>';
                    urls.forEach(url => {
                        hoverinfo += `<li>${url}</li>`;
                    });
                    hoverinfo += '</ul>';
                }
                hoverinfo += '</div>';
                return hoverinfo;
            }
        }
    });
}

window.addEventListener('resize', function(){
    if (map) {
        map.resize()
    }
})

document.addEventListener('DOMContentLoaded', () => {
    // Load topics only
    loadDailyTopics();

    // --- Modal Logic ---
    const helpIcon = document.getElementById('helpIcon');
    const modalOverlay = document.getElementById('modalOverlay');
    const modalClose = document.getElementById('modalClose');

    if (helpIcon && modalOverlay && modalClose) {
        helpIcon.addEventListener('click', () => {
            modalOverlay.classList.add('visible');
        });

        modalClose.addEventListener('click', () => {
            modalOverlay.classList.remove('visible');
        });

        // Optional: Close modal by clicking on the overlay
        modalOverlay.addEventListener('click', (e) => {
            if (e.target === modalOverlay) {
                modalOverlay.classList.remove('visible');
            }
        });
    }
});

function articlesToFills(data){
    const formattedData = {};
    for (let iso in data){
        if (data[iso] && data[iso].articles && data[iso].articles.length > 0) {
            formattedData[iso] = {
                fillKey: 'NO_BIAS'
            };
        }
    }
    return formattedData;
}

function formatDate(input){
  const d = new Date(input)
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${mm}/${dd}`
}

searchBarEl.addEventListener('keyup', function(e) {
    if (e.key === 'Enter') {
        search();
    }
});

searchButtonEl.onclick = async function(e){
    search();
}

async function search(){
    searchButtonEl.disabled = true;
    searchButtonEl.innerHTML = '<div class="loader"></div>';

    const separator = document.querySelector('.section-separator');
    if (separator) {
        separator.textContent = "Loading";
        separator.classList.add('visible');
    }

    const articles_url = new URL(url_base + "query", window.location.origin)

    let query_str = searchBarEl.value

    if (query_str == '') {
        searchButtonEl.disabled = false;
        searchButtonEl.innerHTML = 'Search';
        return
    }

    // Clear previous results and show loading state
    searchResultsEl.innerHTML = '';

    // Last 3 days
    const endDate = moment().format('YYYY-MM-DD');
    const startDate = moment().subtract(3, 'days').format('YYYY-MM-DD');

    const article_params = { query: query_str, date_start: startDate, date_end: endDate };

    Object.keys(article_params).forEach(key => articles_url.searchParams.append(key, article_params[key]))

    // On first search: initialize map under the bar
    if (scrapedISOs.size === 0) { // Only initialize if no countries are known to be scraped
        // Show map container before initializing so dimensions are available
        document.body.classList.remove('landing');
        const end = moment().format('YYYY-MM-DD');
        const start = moment().subtract(2, 'days').format('YYYY-MM-DD');
        await updateMapForDateRange(start, end);
    }

    const response = await fetch(articles_url)
    const { summary, articles } = await response.json()

    // Add any newly found countries from this search to our master list
    Object.keys(articles).forEach(iso => scrapedISOs.add(iso));

    // Reset map colors based on search results for all known scraped countries
    const searchMapData = {};
    for (const iso of scrapedISOs) {
        if (articles[iso] && articles[iso].articles.length > 0) {
            searchMapData[iso] = { fillKey: 'NO_BIAS' }; // Has articles, default to no bias
        } else {
            searchMapData[iso] = { fillKey: 'NO_ARTICLES' }; // Scraped, but no articles for this query
        }
    }
    map.updateChoropleth(searchMapData);

    // Apply summary overrides and render the comprehensive legend
    applySummaryToMap(summary);

    searchResultsEl.innerHTML = ''
    if (separator) separator.classList.remove('visible'); // Hide on new search, will be shown if results exist

    if (Object.keys(articles).length === 0) {
        searchResultsEl.innerHTML = '<p>No results found for this query.</p>';
        searchButtonEl.disabled = false;
        searchButtonEl.innerHTML = 'Search';
        return;
    }

    if (separator) {
        separator.textContent = "Articles";
        separator.classList.add('visible');
    }

    // Get the country ISO codes and sort them by the number of articles in descending order
    const sortedISOs = Object.keys(articles).sort((a, b) => {
        const aLength = articles[a].articles ? articles[a].articles.length : 0;
        const bLength = articles[b].articles ? articles[b].articles.length : 0;
        return bLength - aLength;
    });

    const isosWithMultipleArticles = sortedISOs.filter(iso => articles[iso].articles && articles[iso].articles.length > 1);
    const isosWithSingleArticle = sortedISOs.filter(iso => articles[iso].articles && articles[iso].articles.length === 1);

    const renderCountryArticles = (iso, targetEl) => {
        const countryData = articles[iso];
        const countryName = countryData.country_name;
        const countryArticles = countryData.articles;

        let countryEl = document.createElement('ul')
        let anchorEl = document.createElement('a')
        let toggleEl = document.createElement('div')

        anchorEl.textContent = countryName + ' (' + countryArticles.length + ' Results)'
        anchorEl.href = '#' + iso
        anchorEl.id = iso
        anchorEl.classList.add('iso')

        toggleEl.textContent = '[–]';
        toggleEl.classList.add('toggle')

        function toggle(){
            let toggleState = true;
            return function(){
                if (toggleState)
                    toggleEl.textContent = '[+]'
                else
                    toggleEl.textContent = '[–]'
                toggleState = !toggleState;

                let items = countryEl.getElementsByTagName('li')
                for (let item of items){
                    item.classList.toggle('collapse')
                }
            }
        }

        toggleEl.addEventListener('click', toggle())

        countryEl.appendChild(anchorEl)
        countryEl.appendChild(toggleEl)

        for (let result of countryArticles){
            let dateStr = formatDate(result.publish_at)
            let url = result.article_url

            let resultEl = document.createElement('li')

            let dateEl = document.createElement('div')
            let dateTextEl = document.createTextNode(dateStr)
            dateEl.classList.add('date')
            dateEl.appendChild(dateTextEl)

            let urlEl = document.createElement('a')
            let textEl = document.createTextNode(result.title)
            urlEl.title = result.title
            urlEl.appendChild(textEl)

            if (result.lang == 'en')
                urlEl.href = url
            else
                urlEl.href = 'https://translate.google.com/translate?hl=&sl=auto&tl=en&u=' + url

            resultEl.appendChild(dateEl)
            resultEl.appendChild(urlEl)

            countryEl.appendChild(resultEl)
        }
        targetEl.appendChild(countryEl);
    };

    // Render countries with multiple articles first
    isosWithMultipleArticles.forEach(iso => renderCountryArticles(iso, searchResultsEl));

    // Conditionally render single-article countries
    const shouldHideSingles = isosWithMultipleArticles.length > 0 && isosWithSingleArticle.length > 0;

    if (shouldHideSingles) {
        const showMoreContainer = document.createElement('div');
        showMoreContainer.id = 'show-more-container';
        searchResultsEl.appendChild(showMoreContainer);

        const showMoreButton = document.createElement('button');
        showMoreButton.id = 'show-more-button';
        showMoreButton.className = 'show-more-button';
        showMoreButton.textContent = 'Show more';
        showMoreContainer.appendChild(showMoreButton);

        const singleArticlesContainer = document.createElement('div');
        singleArticlesContainer.id = 'single-articles-container';
        singleArticlesContainer.style.display = 'none'; // Initially hidden
        searchResultsEl.appendChild(singleArticlesContainer);

        isosWithSingleArticle.forEach(iso => renderCountryArticles(iso, singleArticlesContainer));

        showMoreButton.addEventListener('click', () => {
            singleArticlesContainer.style.display = 'block';
            showMoreContainer.remove(); // Remove the button and its container
        });
    } else {
        // Render single-article countries directly if the condition isn't met
        isosWithSingleArticle.forEach(iso => renderCountryArticles(iso, searchResultsEl));
    }

    searchButtonEl.disabled = false;
    searchButtonEl.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
            </svg>
        `;
}

function applySummaryToMap(summary){
    if (!map) return;

    const groups = Array.isArray(summary) ? summary : [];

    const fillNames = ['yellow','blue','red','green'];
    const fillHex = {
        yellow: '#F5D442',
        blue: '#6EA7F2',
        red: '#E86E6E',
        green: '#68C67C',
        NO_BIAS: '#A9A9A9',
        NO_ARTICLES: '#FFFFFF',
    };

    // Override NO_BIAS countries with their group color
    const dataUpdates = {};
    for (let i = 0; i < groups.length && i < fillNames.length; i++){
        const group = groups[i] || {};
        const color = fillNames[i];
        const countries = Array.isArray(group.countries) ? group.countries : [];
        for (const iso of countries){
            dataUpdates[iso] = { fillKey: color };
        }
    }
    map.updateChoropleth(dataUpdates);

    // Render the comprehensive legend
    if (legendEl) {
        legendEl.innerHTML = ''; // Clear previous legend

        const legendItems = [];
        for (let i = 0; i < groups.length && i < fillNames.length; i++){
            const group = groups[i] || {};
            if (group.label) {
                legendItems.push({ label: group.label, color: fillHex[fillNames[i]] });
            }
        }

        legendItems.push({ label: 'No Bias', color: fillHex.NO_BIAS });
        legendItems.push({ label: 'No Articles', color: fillHex.NO_ARTICLES });
        legendItems.push({ label: 'Not Scraped', color: 'rgba(0,0,0,0)' });

        for (const itemData of legendItems) {
            const item = document.createElement('div');
            item.className = 'legend-item';

            const swatch = document.createElement('div');
            swatch.className = 'legend-swatch';
            swatch.style.backgroundColor = itemData.color;
            if (itemData.label === 'Not Scraped') {
                swatch.classList.add('transparent');
            }

            const label = document.createElement('span');
            label.className = 'legend-label';
            label.textContent = itemData.label;

            item.appendChild(swatch);
            item.appendChild(label);
            legendEl.appendChild(item);
        }
    }
}

