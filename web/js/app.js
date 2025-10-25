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

                    // Find the parent ul element (countryEl) to highlight
                    const countryEl = targetElement.closest('ul');
                    if (countryEl) {
                        countryEl.classList.add('highlight');
                        setTimeout(() => {
                            countryEl.classList.remove('highlight');
                        }, 1000);
                    }
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

    // Choose API endpoint: 'query2' for spectrum analysis, 'query' for legacy
    const API_ENDPOINT = 'query2';  // Change to 'query' for legacy summary-based results

    const apiUrl = `/api/${API_ENDPOINT}?query=${encodeURIComponent(query_str)}&date_start=${startDate}&date_end=${endDate}`;
    const response = await fetch(apiUrl);
    const data = await response.json();

    // Render based on whether spectrum data is present
    if (data.spectrum_points && data.spectrum_points.length > 0) {
        renderSpectrumAnalysis(data);
    } else {
        renderSearchResults(data);
    }

    resetSearchButton();
}

/**
 * Renders spectrum analysis data with colored spectrum points and striped country patterns.
 * Expects data format: { spectrum_name, spectrum_description, spectrum_points: [{point_id, label}], articles: {ISO: {country, articles: [...]}} }
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

    // Calculate point_id distribution for each country
    const countryDistributions = {};
    Object.keys(articles).forEach(iso => {
        const countryArticles = articles[iso].articles;
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

        const avgPointId = count > 0 ? totalPointId / count : null; // Keep as float for interpolation
        const roundedAvgPointId = avgPointId !== null ? Math.round(avgPointId) : null;

        // Calculate standard deviation
        let stdDev = null;
        if (count > 1) {
            const variance = countryArticles.reduce((sum, article) => {
                if (article.point_id !== null && article.point_id !== undefined) {
                    return sum + Math.pow(article.point_id - avgPointId, 2);
                }
                return sum;
            }, 0) / count;
            stdDev = Math.sqrt(variance);
        }

        countryDistributions[iso] = {
            distribution,
            avgPointId, // Float value for color interpolation
            roundedAvgPointId, // Integer for discrete color selection if needed
            stdDev, // Standard deviation
            total: count
        };
    });

    // Update map with interpolated colors
    updateMapWithStripes(articles, countryDistributions, spectrum_points, pointIdToColor);

    // Render spectrum legend
    renderSpectrumLegend(spectrum_points, pointIdToColor);

    // Clear and render results
    searchResultsEl.innerHTML = '';
    if (separator) {
        separator.textContent = 'Articles';
        separator.classList.add('visible');
    }

    // Filter countries with at least 3 articles, then sort by average point_id
    const sortedCountries = Object.keys(articles)
        .filter(iso => articles[iso].articles.length >= 3)
        .sort((a, b) => {
            const avgA = countryDistributions[a].avgPointId;
            const avgB = countryDistributions[b].avgPointId;
            return avgA - avgB;
        });

    // Render each country's articles
    sortedCountries.forEach(iso => {
        const countryData = articles[iso];
        const dist = countryDistributions[iso];

        const countryEl = document.createElement('ul');
        countryEl.classList.add('hide-scrollbar');
        const headerEl = document.createElement('div');
        headerEl.className = 'country-header hide-scrollbar';

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

        // Create mini spectrum with marker and error bars
        const miniSpectrum = createMiniSpectrum(dist.avgPointId, dist.stdDev, spectrum_points, pointIdToColor);

        const anchorEl = document.createElement('a');
        anchorEl.textContent = `${countryData.country} (${countryData.articles.length} Results)`;
        anchorEl.href = '#' + iso;
        anchorEl.id = iso;
        anchorEl.classList.add('iso');

        headerEl.appendChild(miniSpectrum);
        headerEl.appendChild(anchorEl);
        countryEl.appendChild(headerEl);
        headerEl.appendChild(toggleEl);

        // Sort articles by point_id, then by similarity (if exists), then by date (most recent first)
        const sortedArticles = [...countryData.articles].sort((a, b) => {
            // Primary sort: by point_id (ascending)
            if (a.point_id !== b.point_id) {
                return (a.point_id || 0) - (b.point_id || 0);
            }

            // Secondary sort: by similarity (descending) if it exists
            if (a.similarity !== undefined && b.similarity !== undefined) {
                return b.similarity - a.similarity;
            }

            // Tertiary sort: by publish_at date (most recent first) if it exists
            if (a.publish_at && b.publish_at) {
                return new Date(b.publish_at) - new Date(a.publish_at);
            }

            return 0;
        });

        // Render articles
        sortedArticles.forEach(article => {
            const resultEl = document.createElement('li');

            // Article color indicator
            const colorBox = document.createElement('div');
            colorBox.className = 'article-color-box';
            colorBox.style.backgroundColor = article.point_id !== null ? pointIdToColor[article.point_id] : '#ccc';

            // Date
            const dateEl = document.createElement('div');
            dateEl.className = 'date';
            if (article.publish_at) {
                dateEl.textContent = formatDate(article.publish_at);
            }

            // Article link
            const urlEl = document.createElement('a');
            urlEl.textContent = article.title;
            urlEl.title = article.title;
            urlEl.target = '_blank';

            // Use Google Translate link for non-English articles
            if (article.lang === 'en') {
                urlEl.href = article.url;
            } else {
                urlEl.href = 'https://translate.google.com/translate?hl=&sl=auto&tl=en&u=' + article.url;
            }

            resultEl.appendChild(colorBox);
            resultEl.appendChild(dateEl);
            resultEl.appendChild(urlEl);
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

function createMiniSpectrum(avgPointId, stdDev, spectrum_points, pointIdToColor) {
    const sortedPoints = [...spectrum_points].sort((a, b) => a.point_id - b.point_id);
    const minPointId = sortedPoints[0].point_id;
    const maxPointId = sortedPoints[sortedPoints.length - 1].point_id;

    // Extend the spectrum range by 0.5 on each side
    const spectrumMin = minPointId - 0.5;
    const spectrumMax = maxPointId + 0.5;
    const spectrumRange = spectrumMax - spectrumMin;

    // Build gradient
    const gradientStops = sortedPoints.map(point => {
        const position = ((point.point_id - spectrumMin) / spectrumRange) * 100;
        return `${pointIdToColor[point.point_id]} ${position}%`;
    }).join(', ');

    // Create mini spectrum container
    const miniSpectrum = document.createElement('div');
    miniSpectrum.className = 'country-mini-spectrum';
    miniSpectrum.style.background = `linear-gradient(to right, ${gradientStops})`;

    // Add marker/error bar if avgPointId exists
    if (avgPointId !== null && avgPointId !== undefined) {
        const markerPosition = ((avgPointId - spectrumMin) / spectrumRange) * 100;

        if (stdDev !== null && stdDev !== undefined && stdDev > 0) {
            // Show rectangle spanning mean ± stdDev
            const lowerBound = Math.max(spectrumMin, avgPointId - stdDev);
            const upperBound = Math.min(spectrumMax, avgPointId + stdDev);
            const lowerPosition = ((lowerBound - spectrumMin) / spectrumRange) * 100;
            const upperPosition = ((upperBound - spectrumMin) / spectrumRange) * 100;

            const marker = document.createElement('div');
            marker.className = 'country-spectrum-marker';
            marker.style.left = `${lowerPosition}%`;
            marker.style.width = `${upperPosition - lowerPosition}%`;
            miniSpectrum.appendChild(marker);
        } else {
            // Show 3px rectangle at mean if no variance
            const marker = document.createElement('div');
            marker.className = 'country-spectrum-marker';
            marker.style.left = `${markerPosition}%`;
            marker.style.width = '3px';
            miniSpectrum.appendChild(marker);
        }
    }

    return miniSpectrum;
}

function interpolateSpectrumColor(avgPointId, spectrum_points, pointIdToColor) {
    // Interpolate color based on float avgPointId value
    if (avgPointId === null || avgPointId === undefined) return '#ccc';

    const sortedPoints = [...spectrum_points].sort((a, b) => a.point_id - b.point_id);
    const minPointId = sortedPoints[0].point_id;
    const maxPointId = sortedPoints[sortedPoints.length - 1].point_id;

    // Clamp to range
    const clampedAvg = Math.max(minPointId, Math.min(maxPointId, avgPointId));

    // Find the two points to interpolate between
    let lowerPoint = sortedPoints[0];
    let upperPoint = sortedPoints[sortedPoints.length - 1];

    for (let i = 0; i < sortedPoints.length - 1; i++) {
        if (clampedAvg >= sortedPoints[i].point_id && clampedAvg <= sortedPoints[i + 1].point_id) {
            lowerPoint = sortedPoints[i];
            upperPoint = sortedPoints[i + 1];
            break;
        }
    }

    // If exactly on a point, return that color
    if (clampedAvg === lowerPoint.point_id) {
        return pointIdToColor[lowerPoint.point_id];
    }
    if (clampedAvg === upperPoint.point_id) {
        return pointIdToColor[upperPoint.point_id];
    }

    // Interpolate between the two colors
    const ratio = (clampedAvg - lowerPoint.point_id) / (upperPoint.point_id - lowerPoint.point_id);
    const lowerColor = pointIdToColor[lowerPoint.point_id];
    const upperColor = pointIdToColor[upperPoint.point_id];

    // Extract RGB values
    const lowerRGB = lowerColor.match(/\d+/g).map(Number);
    const upperRGB = upperColor.match(/\d+/g).map(Number);

    // Interpolate each channel
    const r = Math.round(lowerRGB[0] + (upperRGB[0] - lowerRGB[0]) * ratio);
    const g = Math.round(lowerRGB[1] + (upperRGB[1] - lowerRGB[1]) * ratio);
    const b = Math.round(lowerRGB[2] + (upperRGB[2] - lowerRGB[2]) * ratio);

    return `rgb(${r}, ${g}, ${b})`;
}

function updateMapWithStripes(articlesByCountry, countryDistributions, spectrum_points, pointIdToColor) {
    if (!map) return;

    // Use setTimeout to ensure map DOM is ready
    setTimeout(() => {
        const svg = document.querySelector('#mapContainer svg');
        if (!svg) return;

        Object.keys(articlesByCountry).forEach(iso => {
            const dist = countryDistributions[iso];

            if (dist.total === 0) return;

            // Get the country path
            const countryPath = svg.querySelector(`.datamaps-subunit.${iso}`);
            if (!countryPath) {
                console.warn(`Country path not found for ISO: ${iso}`);
                return;
            }

            // Use interpolated color based on float average
            const avgColor = interpolateSpectrumColor(dist.avgPointId, spectrum_points, pointIdToColor);
            countryPath.style.fill = avgColor;
        });
    }, 100);
}

function renderSpectrumLegend(spectrum_points, pointIdToColor) {
    if (!legendEl) return;

    legendEl.classList.add('spectrum-legend');
    legendEl.innerHTML = '';

    const title = document.createElement('div');
    title.className = 'spectrum-title';
    title.textContent = 'Spectrum';
    legendEl.appendChild(title);

    const sortedPoints = [...spectrum_points].sort((a, b) => a.point_id - b.point_id);
    const minPointId = sortedPoints[0].point_id;
    const maxPointId = sortedPoints[sortedPoints.length - 1].point_id;

    // Extend the spectrum range by 0.5 on each side
    const spectrumMin = minPointId - 0.5;
    const spectrumMax = maxPointId + 0.5;
    const spectrumRange = spectrumMax - spectrumMin;

    // Create the gradient bar
    const gradientBar = document.createElement('div');
    gradientBar.className = 'spectrum-gradient-bar';
    const gradientStops = sortedPoints.map(point => {
        const position = ((point.point_id - spectrumMin) / spectrumRange) * 100;
        return `${pointIdToColor[point.point_id]} ${position}%`;
    }).join(', ');
    gradientBar.style.background = `linear-gradient(to right, ${gradientStops})`;

    // Add markers positioned absolutely on the gradient bar
    sortedPoints.forEach(point => {
        const position = ((point.point_id - spectrumMin) / spectrumRange) * 100;
        const marker = document.createElement('div');
        marker.className = 'spectrum-marker';
        marker.style.left = `${position}%`;
        gradientBar.appendChild(marker);
    });

    legendEl.appendChild(gradientBar);

    // Create labels container using flexbox for equal distribution
    const labelsContainer = document.createElement('div');
    labelsContainer.className = 'spectrum-labels-container';

    sortedPoints.forEach(point => {
        const label = document.createElement('div');
        label.className = 'spectrum-label';
        label.textContent = point.label;
        if (point.description) {
            label.title = point.description;
        }
        labelsContainer.appendChild(label);
    });

    legendEl.appendChild(labelsContainer);
}

/**
 * Renders search results from API response data (legacy format without spectrum).
 * Expects data format: { summary: [...], articles: { ISO: { country/country_name, articles: [...] } } }
 */
function renderSearchResults(data) {
    const { summary, articles } = data;

    // Normalize country name field (handle both 'country' and 'country_name')
    Object.keys(articles).forEach(iso => {
        if (articles[iso].country && !articles[iso].country_name) {
            articles[iso].country_name = articles[iso].country;
        }
    });

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
                countryEl.classList.add('hide-scrollbar')
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
