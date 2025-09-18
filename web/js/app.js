const searchButtonEl = document.getElementById("submitQuery");
const searchBarEl = document.getElementById("search");
const searchResultsEl = document.getElementById("searchResults");
const topicsContainerEl = document.getElementById("topicsContainer");
const summaryEl = document.getElementById("summary");

const url_base = "/api/";

let map; // Will be initialized after fetching paper data
let origMapData = {}; // Holds the base state of the map for the current date range
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
        .filter(id => id !== '-99'); // Exclude the invalid country code

    const noDataColor = 'rgba(222, 222, 222, 0.6)';
    const defaultFillColor = 'rgba(182, 184, 196, 0.6)';

    allCountries.forEach(countryIso => {
        if (!papersByCountry[countryIso]) {
            origMapData[countryIso] = { fillColor: noDataColor };
        } else {
            origMapData[countryIso] = { fillColor: defaultFillColor };
        }
    });

    // Copy because the map updates in place
    const currentMapData = { ...origMapData };

    map = new Datamap({
        element: document.getElementById('map'),
        projection: 'mercator',
        fills: {
            defaultFill: defaultFillColor,
            yellow: '#F5D442',
            blue: '#6EA7F2',
            red: '#E86E6E',
            green: '#68C67C'
        },
        data: currentMapData,
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
    const articlesByCountry = Object.values(data);
    if (articlesByCountry.length === 0) {
        return {};
    }

    const lengths = articlesByCountry.map(countryData => countryData.articles.length);
    const lengthMin = Math.min(...lengths);
    const lengthMax = Math.max(...lengths);

    // Create a color scale. Handle the edge case of only one value.
    const domain = (lengthMin === lengthMax) ? [0, lengthMax] : [lengthMin, lengthMax];
    const paletteScale = d3.scale.linear()
            .domain(domain)
            .range(["#a0a0f6", "#02386F"]); // Light to dark

    for (let iso in data){
        formattedData[iso] = {
            fillColor: paletteScale(data[iso].articles.length)
        };
    }

    return formattedData;
}

function formatDate(input){
  const d = new Date(input)
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const yy = String(d.getFullYear() % 100).padStart(2, '0')
  return `${mm}/${dd}/${yy}`
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

    const articles_url = new URL(url_base + "query", window.location.origin)
    const stats_url = new URL(url_base + "stats", window.location.origin)

    let query_str = searchBarEl.value

    if (query_str == '') {
        searchButtonEl.disabled = false;
        searchButtonEl.innerHTML = 'Search';
        return
    }

    // Last 3 days
    const endDate = moment().format('YYYY-MM-DD');
    const startDate = moment().subtract(2, 'days').format('YYYY-MM-DD');

    const article_params = { query: query_str, date_start: startDate, date_end: endDate };
    const stat_params = {
        query: query_str,
        date_start: moment(startDate).subtract(10, 'days').format('YYYY-MM-DD'),
        date_end: moment(endDate).add(10, 'days').format('YYYY-MM-DD')
    };

    Object.keys(article_params).forEach(key => articles_url.searchParams.append(key, article_params[key]))
    Object.keys(stat_params).forEach(key => stats_url.searchParams.append(key, stat_params[key]))

    // On first search: initialize map under the bar
    if (!hasSearchedOnce) {
        // Show map container before initializing so dimensions are available
        document.body.classList.remove('landing');
        const end = moment().format('YYYY-MM-DD');
        const start = moment().subtract(2, 'days').format('YYYY-MM-DD');
        await updateMapForDateRange(start, end);
        hasSearchedOnce = true;
    }

    const response = await fetch(articles_url)
    const { summary, articles } = await response.json()

    const searchData = articlesToFills(articles);
    const newMapData = { ...origMapData, ...searchData };

    map.updateChoropleth(newMapData);

    // Apply structured summary groups to map fills and legend (Datamaps built-in)
    applySummaryToMap(summary)

    searchResultsEl.innerHTML = ''

    if (Object.keys(data).length === 0) {
        searchResultsEl.innerHTML = '<p>No results found for this query.</p>';
        searchButtonEl.disabled = false;
        searchButtonEl.innerHTML = 'Search';
        return;
    }

    for (let iso in data){
        const countryData = data[iso];
        const countryName = countryData.country_name;
        const articles = countryData.articles;

        let countryEl = document.createElement('ul')
        let anchorEl = document.createElement('a')
        let toggleEl = document.createElement('div')

        anchorEl.textContent = countryName + ' (' + articles.length + ' Results)'
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

        for (let result of articles){
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

            // Add minimal domain (no http/https or www)
            let domainEl = document.createElement('span')
            domainEl.className = 'domain'
            domainEl.textContent = new URL(url).hostname.replace(/^www\./, '') + ' (' + parseInt(result.similarity * 100) + ') '

            resultEl.appendChild(dateEl)
            resultEl.appendChild(domainEl)
            resultEl.appendChild(urlEl)

            countryEl.appendChild(resultEl)
        }

        searchResultsEl.appendChild(countryEl)
    }

    searchButtonEl.disabled = false;
    searchButtonEl.innerHTML = 'Search';
}

function applySummaryToMap(summary){
    // Define fill names and colors in order; extend as needed
    const fillNames = ['yellow','blue','red','green'];

    // Extend fills with our group colors
    const labels = {};
    const dataUpdates = {};

    for (let i = 0; i < summary.length && i < fillNames.length; i++){
        const group = summary[i] || {};
        const color = fillNames[i];
        for (const iso of group.countries){
            dataUpdates[iso] = { fillKey: color };
        }
        labels[color] = group.label;
    }

    map.updateChoropleth(dataUpdates);

    map.legend({ labels });
}

