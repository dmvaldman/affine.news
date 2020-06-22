const searchButtonEl = document.getElementById("submitQuery");
const searchQueryEl = document.getElementById("search");
const searchResultsEl = document.getElementById("searchResults");

url_base = "http://localhost:8000/"
// url_base = "https://affine-news.appspot.com/"

let map = new Datamap({
    element: document.getElementById('map'),
    projection: 'mercator',
    fills: {
        defaultFill: 'rgba(182,184,196,0.9)' // Any hex, color name or rgb/rgba value
    },
    geographyConfig: {
        highlightOnHover: false
    },
    done: function(datamap) {
        datamap.svg.selectAll('.datamaps-subunit').on('click', function(geography) {
            let el = document.getElementById(geography.properties.name)
            if (el) el.click()
        })
    }
});

$(function() {
    $('input[name="dates"]').daterangepicker({
        opens: 'left',
        ranges: {
            'Today': [moment(), moment()],
           'Yesterday': [moment().subtract(1, 'days'), moment().subtract(1, 'days')],
           'Last 7 Days': [moment().subtract(6, 'days'), moment()],
           'Last 30 Days': [moment().subtract(29, 'days'), moment()],
           'This Month': [moment().startOf('month'), moment().endOf('month')],
           'Last Month': [moment().subtract(1, 'month').startOf('month'), moment().subtract(1, 'month').endOf('month')]
        }
    }, function(start, end, label) {
        console.log("A new date selection was made: " + start.format('YYYY-MM-DD') + ' to ' + end.format('YYYY-MM-DD'));
    });
});

const countryToISO = {
    'USA': 'USA',
    'Sweden': 'SWE',
    'Italy': 'ITA',
    'France': 'FRA',
    'Spain': 'ESP',
    'China': 'CHN',
    'Poland': 'POL',
    'Ukraine': 'UKR',
    'Syria': 'SYR',
    'Russia': 'RUS',
    'Iraq': 'IRQ',
    'Iran': 'IRN',
    'Turkey': 'TUR',
    'Qatar': 'QAT',
    'Hong Kong': 'HKG',
    'Brazil': 'BRA'
}

function formatData(data){
    let formattedData = {}
    let lengthMin = Infinity
    let lengthMax = -Infinity

    for (let country in data){
        let iso = countryToISO[country]
        formattedData[iso] = data[country]

        let length = data[country].length
        if (length > lengthMin) lengthMin = length
        if (length < lengthMax) lengthMax = length
    }

    let paletteScale = d3.scale.linear()
            .domain([lengthMin,lengthMax])
            .range([
                "#EFEFFF",
                "#02386F"]
            );

    for (let country in data){
        let iso = countryToISO[country]
        formattedData[iso] = Object.assign({}, data[country])
        formattedData[iso]['fillColor'] = paletteScale(data[country].length)
    }

    return formattedData
}

searchQueryEl.onkeypress = function(e){
    let code = (e.keyCode ? e.keyCode : e.which);
    if (code == 13) {
        search()
    }
}

searchButtonEl.onclick = function(e){
    search()
}

function search(){
    const url = new URL(url_base + "query")

    let query_str = searchQueryEl.value
    console.log(query_str)

    const dates = $('input[name="dates"]')[0].value.split(' - ')

    const date_start = dates[0]
    const date_end = dates[1]

    const params = {
        query: query_str,
        date_start: date_start,
        date_end: date_end
    }

    Object.keys(params).forEach(key => url.searchParams.append(key, params[key]))

    fetch(url)
        .then(function(response){
            return response.json();
        })
        .then(function(data){

            map.updateChoropleth(formatData(data), {reset: true})

            searchResultsEl.innerHTML = ''

            for (let country in data){
                let countryEl = document.createElement('ul')
                let anchorEl = document.createElement('a')
                anchorEl.textContent = country + ' (' + data[country].length + ')'
                anchorEl.href = '#' + country
                anchorEl.name = country
                anchorEl.id = country
                countryEl.appendChild(anchorEl)

                for (let result in data[country]){
                    let date = new Date(data[country][result].publish_at).toDateString()
                    let url = data[country][result].article_url

                    let resultEl = document.createElement('li')

                    let dateEl = document.createElement('div')
                    let dateTextEl = document.createTextNode(date)
                    dateEl.classList.add('date')
                    dateEl.appendChild(dateTextEl)

                    let urlEl = document.createElement('a')
                    let textEl = document.createTextNode(data[country][result].title)
                    urlEl.appendChild(textEl)

                    urlEl.href = 'https://translate.google.com/translate?hl=&sl=auto&tl=en&u=' + url

                    resultEl.appendChild(dateEl)
                    resultEl.appendChild(urlEl)

                    countryEl.appendChild(resultEl)
                }

                searchResultsEl.appendChild(countryEl)
            }

            console.log(data)
        })
}