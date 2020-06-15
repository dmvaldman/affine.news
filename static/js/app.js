const searchButtonEl = document.getElementById("submitQuery");
const searchQueryEl = document.getElementById("search");
const searchResultsEl = document.getElementById("searchResults");

url_base = "http://localhost:8000/"
// url_base = "https://affine-news.appspot.com/"

var countriesPath = 'static/data/countries.geo.json';

function getColor(data) {
    let d = 0
    if (data instanceof Array)  d = data.length
    return d > 7 ? '#800026':
        d > 20 ? '#BD0026':
        d > 10 ? '#E31A1C':
        d > 5 ? '#FC4E2A':
        d > 2 ? '#FD8D3C':
        d > 1 ? '#FEB24C':
        d > 0 ? '#FED976':
                '#FFEDA0';
}

function style(feature) {
    return {
        fillColor: getColor(feature.properties.affine),
        weight: 1,
        opacity: 1,
        color: 'white',
        dashArray: '1',
        fillOpacity: 0.7
    };
}


let geojsonLayer = null;
let geojsonData = null;
let map = null;

fetch(url_base + countriesPath)
    .then(response => response.json())
    .then(data => {
        map = L.map('map').setView([45, 0], 1);
        geojsonData = data
        geojsonData = updateData(data, {})
        geojsonLayer = L.geoJson(geojsonData, {
            clickable: false,
            style: style
        }).addTo(map);
});

$(function() {
    $('input[name="dates"]').daterangepicker({
        opens: 'left'
    }, function(start, end, label) {
        console.log("A new date selection was made: " + start.format('YYYY-MM-DD') + ' to ' + end.format('YYYY-MM-DD'));
    });
});

function updateData(data, patch){
    for (let index in geojsonData.features){
        let countryData = geojsonData.features[index].properties
        countryData['affine'] = patch[countryData.name]
    }
    return data
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

            map.removeLayer(geojsonLayer)
            geojsonData = updateData(geojsonData, data)
            geojsonLayer = L.geoJson(geojsonData, {
                clickable: false,
                style: style
            }).addTo(map);

            searchResultsEl.innerHTML = ''

            for (let country in data){
                let countryEl = document.createElement('ul')
                countryEl.textContent = country

                for (let result in data[country]){
                    let resultEl = document.createElement('li')
                    let urlEl = document.createElement('a')
                    let textEl = document.createTextNode(data[country][result].title)
                    urlEl.appendChild(textEl)
                    urlEl.href = 'https://translate.google.com/translate?hl=&sl=auto&tl=en&u=' + data[country][result].article_url
                    resultEl.appendChild(urlEl)
                    countryEl.appendChild(resultEl)
                }

                searchResultsEl.appendChild(countryEl)
            }

            console.log(data)
        })
}