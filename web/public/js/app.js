const searchButtonEl = document.getElementById("submitQuery");
const searchQueryEl = document.getElementById("search");
const searchResultsEl = document.getElementById("searchResults");

const url_base = "/api/";

let map = new Datamap({
    element: document.getElementById('map'),
    projection: 'mercator',
    fills: {
        defaultFill: 'rgba(182,184,196,0.6)'
    },
    responsive: true,
    geographyConfig: {
        highlightOnHover: false
    },
    done: function(datamap) {
        datamap.svg.selectAll('.datamaps-subunit').on('click', function(geography) {
            let el = document.getElementById(geography.id)
            if (el) el.click()
        })
    }
});

window.addEventListener('resize', function(){
    map.resize()
})

$(function() {
    $('input[name="dates"]').daterangepicker({
        opens: 'left',
        startDate: moment().subtract(6, 'days'),
        endDate: moment(),
        locale: {
          format: 'YYYY-MM-DD'
        },
        ranges: {
            'Today': [moment(), moment()],
            'Yesterday': [moment().subtract(1, 'days'), moment().subtract(1, 'days')],
            'Last 3 Days': [moment().subtract(2, 'days'), moment()],
            'Last 7 Days': [moment().subtract(6, 'days'), moment()],
            'Last 30 Days': [moment().subtract(29, 'days'), moment()]
        }
    });
});

function formatData(data){
    let formattedData = {}
    let lengthMin = -Infinity
    let lengthMax = Infinity

    for (let iso in data){
        formattedData[iso] = iso

        let length = data[iso].length
        if (length > lengthMin) lengthMin = length
        if (length < lengthMax) lengthMax = length
    }

    let paletteScale = d3.scale.linear()
            .domain([lengthMin,lengthMax])
            .range([
                "#02386F",
                "#a0a0f6"
                ]
            );

    for (let iso in data){
        formattedData[iso] = Object.assign({}, data[iso])
        formattedData[iso]['fillColor'] = paletteScale(data[iso].length)
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
    const articles_url = new URL(url_base + "query", window.location.origin)
    const stats_url = new URL(url_base + "stats", window.location.origin)

    let query_str = searchQueryEl.value

    const dates = $('input[name="dates"]').val().split(' - ')

    const date_start = dates[0]
    const date_end = dates[1]

    const article_params = {
        query: query_str,
        date_start: date_start,
        date_end: date_end
    }

    const stat_params = {
        query: query_str,
        date_start: moment(date_start).subtract(10, 'days').format('YYYY-MM-DD'),
        date_end: moment(date_end).add(10, 'days').format('YYYY-MM-DD')
    }

    Object.keys(article_params).forEach(key => articles_url.searchParams.append(key, article_params[key]))
    Object.keys(stat_params).forEach(key => stats_url.searchParams.append(key, stat_params[key]))

    fetch(articles_url)
        .then(function(response){
            return response.json();
        })
        .then(function(data){

            map.updateChoropleth(formatData(data), {reset: true})

            searchResultsEl.innerHTML = ''

            for (let country in data){
                let countryEl = document.createElement('ul')
                let anchorEl = document.createElement('a')
                let toggleEl = document.createElement('div')

                anchorEl.textContent = country + ' (' + data[country].length + ' Results)'
                anchorEl.href = '#' + country
                anchorEl.name = country
                anchorEl.id = country
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
                    urlEl.title = data[country][result].title
                    urlEl.appendChild(textEl)

                    if (data[country][result].lang == 'en')
                        urlEl.href = url
                    else
                        urlEl.href = 'https://translate.google.com/translate?hl=&sl=auto&tl=en&u=' + url

                    resultEl.appendChild(dateEl)
                    resultEl.appendChild(urlEl)

                    countryEl.appendChild(resultEl)
                }

                searchResultsEl.appendChild(countryEl)
            }
        })

    fetch(stats_url)
        .then(function(response){
            return response.json();
        })
        .then(function(data){
            console.log('stats response', data)
        })
}


