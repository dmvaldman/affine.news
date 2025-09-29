const searchButtonEl = document.getElementById("submitQuery");
const searchBarEl = document.getElementById("search");
const searchResultsEl = document.getElementById("searchResults");
const topicsContainerEl = document.getElementById("topicsContainer");
const summaryEl = document.getElementById("summary");
const legendEl = document.getElementById("legend");
const separator = document.querySelector('.section-separator');

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
                    const singleArticlesContainer = document.getElementById('single-articles-container');
                    const showMoreContainer = document.getElementById('show-more-container');

                    // If the target is in the hidden "Show more" section, expand it first.
                    if (singleArticlesContainer && singleArticlesContainer.contains(targetElement) && singleArticlesContainer.style.display === 'none') {
                        singleArticlesContainer.style.display = 'block';
                        if (showMoreContainer) {
                            showMoreContainer.remove();
                        }
                    }

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

function resetMap() {
    if (map) {
        map.updateChoropleth(origMapData);
    }
    if (legendEl) {
        legendEl.innerHTML = '';
    }
}

function resetSearchButton() {
    searchButtonEl.disabled = false;
    searchButtonEl.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
        </svg>
    `;
}

async function search(){
    searchButtonEl.disabled = true;
    searchButtonEl.innerHTML = '<div class="loader"></div>';

    if (separator) {
        separator.textContent = "Loading";
        separator.classList.add('visible');
    }

    const articles_url = new URL(url_base + "query", window.location.origin)

    let query_str = searchBarEl.value

    if (query_str == '') {
        resetSearchButton();
        return
    }

    // Clear previous results and show loading state
    searchResultsEl.innerHTML = '';
    resetMap();

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

    // TEMPORARY: Use mock spectrum analysis data
    const response = await fetch('/static/spectrum_analysis_Moldova_election_interference.json')
    const data = await response.json()

    renderSpectrumAnalysis(data);
    // renderSearchResults(data); // Original API rendering - commented out for spectrum experiment
    resetSearchButton();
}

/**
 * Renders spectrum analysis data with colored spectrum points and striped country patterns.
 * Expects data format: { spectrum_name, spectrum_description, spectrum_points: [{point_id, label}], articles: [{title, url, iso, country, point_id}] }
 */
function renderSpectrumAnalysis(data) {
    const { spectrum_name, spectrum_description, spectrum_points, articles } = data;

    if (!articles || !spectrum_points) {
        console.error("Invalid spectrum analysis data:", data);
        searchResultsEl.innerHTML = '<p>An error occurred while loading spectrum analysis.</p>';
        return;
    }

    // Create color gradient for spectrum points (red to blue)
    const spectrumColors = generateSpectrumColors(spectrum_points.length);
    const pointIdToColor = {};
    spectrum_points.forEach((point, index) => {
        pointIdToColor[point.point_id] = spectrumColors[index];
    });

    // Group articles by country
    const articlesByCountry = {};
    articles.forEach(article => {
        if (!articlesByCountry[article.iso]) {
            articlesByCountry[article.iso] = {
                country: article.country,
                iso: article.iso,
                articles: []
            };
        }
        articlesByCountry[article.iso].articles.push(article);
    });

    // Calculate point_id distribution for each country
    const countryDistributions = {};
    Object.keys(articlesByCountry).forEach(iso => {
        const countryArticles = articlesByCountry[iso].articles;
        const distribution = {};
        let totalPointId = 0;
        let count = 0;

        countryArticles.forEach(article => {
            if (article.point_id !== null && article.point_id !== undefined) {
                distribution[article.point_id] = (distribution[article.point_id] || 0) + 1;
                totalPointId += article.point_id;
                count++;
            }
        });

        const avgPointId = count > 0 ? Math.round(totalPointId / count) : null;
        countryDistributions[iso] = {
            distribution,
            avgPointId,
            total: count
        };
    });

    // Update map with striped patterns
    updateMapWithStripes(articlesByCountry, countryDistributions, pointIdToColor);

    // Render spectrum legend
    renderSpectrumLegend(spectrum_points, pointIdToColor);

    // Clear and render results
    searchResultsEl.innerHTML = '';
    if (separator) {
        separator.textContent = spectrum_name;
        separator.classList.add('visible');
    }

    // Sort countries by number of articles
    const sortedCountries = Object.keys(articlesByCountry).sort((a, b) => {
        return articlesByCountry[b].articles.length - articlesByCountry[a].articles.length;
    });

    // Render each country's articles
    sortedCountries.forEach(iso => {
        const countryData = articlesByCountry[iso];
        const dist = countryDistributions[iso];

        const countryEl = document.createElement('ul');
        const headerEl = document.createElement('div');
        headerEl.style.display = 'flex';
        headerEl.style.alignItems = 'center';
        headerEl.style.gap = '8px';

        // Country color indicator (rounded average)
        const colorBox = document.createElement('div');
        colorBox.style.width = '16px';
        colorBox.style.height = '16px';
        colorBox.style.backgroundColor = dist.avgPointId !== null ? pointIdToColor[dist.avgPointId] : '#ccc';
        colorBox.style.flexShrink = '0';

        const anchorEl = document.createElement('a');
        anchorEl.textContent = `${countryData.country} (${countryData.articles.length} Results)`;
        anchorEl.href = '#' + iso;
        anchorEl.id = iso;
        anchorEl.classList.add('iso');

        const toggleEl = document.createElement('div');
        toggleEl.textContent = '[–]';
        toggleEl.classList.add('toggle');

        function createToggle() {
            let toggleState = true;
            return function() {
                toggleEl.textContent = toggleState ? '[+]' : '[–]';
                toggleState = !toggleState;
                const items = countryEl.getElementsByTagName('li');
                for (let item of items) {
                    item.classList.toggle('collapse');
                }
            };
        }

        toggleEl.addEventListener('click', createToggle());

        headerEl.appendChild(colorBox);
        headerEl.appendChild(anchorEl);
        headerEl.appendChild(toggleEl);
        countryEl.appendChild(headerEl);

        // Render articles
        countryData.articles.forEach(article => {
            const resultEl = document.createElement('li');
            resultEl.style.display = 'flex';
            resultEl.style.alignItems = 'flex-start';
            resultEl.style.gap = '8px';

            // Article color indicator
            const articleColorBox = document.createElement('div');
            articleColorBox.style.width = '12px';
            articleColorBox.style.height = '12px';
            articleColorBox.style.marginTop = '4px';
            articleColorBox.style.backgroundColor = article.point_id !== null ? pointIdToColor[article.point_id] : '#ccc';
            articleColorBox.style.flexShrink = '0';

            const contentWrapper = document.createElement('div');
            contentWrapper.style.flex = '1';

            const urlEl = document.createElement('a');
            urlEl.textContent = article.title;
            urlEl.title = article.title;
            urlEl.href = article.url;
            urlEl.target = '_blank';

            contentWrapper.appendChild(urlEl);
            resultEl.appendChild(articleColorBox);
            resultEl.appendChild(contentWrapper);
            countryEl.appendChild(resultEl);
        });

        searchResultsEl.appendChild(countryEl);
    });
}

function generateSpectrumColors(count) {
    // Generate colors from red to blue
    const colors = [];
    for (let i = 0; i < count; i++) {
        const ratio = i / (count - 1 || 1);
        const r = Math.round(220 - ratio * 120); // 220 to 100
        const g = Math.round(50 + ratio * 100);  // 50 to 150
        const b = Math.round(50 + ratio * 200);  // 50 to 250
        colors.push(`rgb(${r}, ${g}, ${b})`);
    }
    return colors;
}

function updateMapWithStripes(articlesByCountry, countryDistributions, pointIdToColor) {
    if (!map) return;

    const mapData = {};

    Object.keys(articlesByCountry).forEach(iso => {
        const dist = countryDistributions[iso];
        const distribution = dist.distribution;
        const total = dist.total;

        if (total === 0) {
            mapData[iso] = { fillKey: 'NO_ARTICLES' };
            return;
        }

        // Calculate percentages for each point_id
        const stripes = [];
        Object.keys(distribution).sort((a, b) => a - b).forEach(pointId => {
            const count = distribution[pointId];
            const percentage = (count / total) * 100;
            const color = pointIdToColor[pointId];
            stripes.push({ color, percentage });
        });

        // Create SVG pattern for diagonal stripes
        const patternId = `stripes-${iso}`;
        mapData[iso] = {
            fillKey: 'CUSTOM',
            fillPattern: createDiagonalStripePattern(patternId, stripes)
        };
    });

    // Update Datamap with custom patterns
    map.updateChoropleth(mapData, { reset: false });

    // Inject SVG patterns into the map
    injectMapPatterns(articlesByCountry, countryDistributions, pointIdToColor);
}

function createDiagonalStripePattern(patternId, stripes) {
    return patternId;
}

function injectMapPatterns(articlesByCountry, countryDistributions, pointIdToColor) {
    if (!map) return;

    // Use setTimeout to ensure map DOM is fully rendered
    setTimeout(() => {
        const svg = document.querySelector('#mapContainer svg');
        if (!svg) {
            console.error('Map SVG not found');
            return;
        }

        let defs = svg.querySelector('defs');
        if (!defs) {
            defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
            svg.insertBefore(defs, svg.firstChild);
        }

        // Clear existing patterns
        defs.innerHTML = '';

        Object.keys(articlesByCountry).forEach(iso => {
            const dist = countryDistributions[iso];
            const distribution = dist.distribution;
            const total = dist.total;

            if (total === 0) return;

            const stripes = [];
            Object.keys(distribution).sort((a, b) => a - b).forEach(pointId => {
                const count = distribution[pointId];
                const percentage = (count / total) * 100;
                const color = pointIdToColor[pointId];
                stripes.push({ color, percentage });
            });

            const patternId = `stripes-${iso}`;
            const pattern = document.createElementNS('http://www.w3.org/2000/svg', 'pattern');
            pattern.setAttribute('id', patternId);
            pattern.setAttribute('patternUnits', 'userSpaceOnUse');
            pattern.setAttribute('width', '100');
            pattern.setAttribute('height', '100');
            pattern.setAttribute('patternTransform', 'rotate(45)');

            let currentX = 0;
            stripes.forEach(stripe => {
                const width = stripe.percentage;
                const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
                rect.setAttribute('x', currentX.toString());
                rect.setAttribute('y', '0');
                rect.setAttribute('width', width.toString());
                rect.setAttribute('height', '100');
                rect.setAttribute('fill', stripe.color);
                pattern.appendChild(rect);
                currentX += width;
            });

            defs.appendChild(pattern);

            // Apply pattern to country path
            const countryPath = svg.querySelector(`.datamaps-subunit.${iso}`);
            if (countryPath) {
                countryPath.style.fill = `url(#${patternId})`;
                console.log(`Applied pattern ${patternId} to ${iso}`, stripes);
            } else {
                console.warn(`Country path not found for ISO: ${iso}`);
            }
        });
    }, 100);
}

function renderSpectrumLegend(spectrum_points, pointIdToColor) {
    if (!legendEl) return;

    legendEl.innerHTML = '<div style="font-weight: bold; margin-bottom: 8px;">Spectrum</div>';

    spectrum_points.forEach(point => {
        const item = document.createElement('div');
        item.style.display = 'flex';
        item.style.alignItems = 'center';
        item.style.gap = '8px';
        item.style.marginBottom = '4px';

        const colorBox = document.createElement('div');
        colorBox.style.width = '16px';
        colorBox.style.height = '16px';
        colorBox.style.backgroundColor = pointIdToColor[point.point_id];
        colorBox.style.flexShrink = '0';

        const label = document.createElement('span');
        label.textContent = point.label;
        label.style.fontSize = '12px';

        item.appendChild(colorBox);
        item.appendChild(label);
        legendEl.appendChild(item);
    });
}

/**
 * Renders search results from API response data.
 * Expects data format: { summary: [...], articles: { ISO: { country_name, articles: [...] } } }
 */
function renderSearchResults(data) {
    const { summary, articles } = data;

    if (!articles) {
        console.error("API response did not include 'articles' object:", data);
        searchResultsEl.innerHTML = '<p>An error occurred while fetching results. Please try again.</p>';
        return;
    }

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
        if (separator) separator.classList.remove('visible');
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
