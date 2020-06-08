const searchButtonEl = document.getElementById("submitQuery");
const searchQueryEl = document.getElementById("search");

searchButtonEl.onclick = function(e){
    const url = new URL("http://localhost:8000/query")

    const query_str = searchQueryEl.value

    const today = new Date()
    const yesterday = new Date(today)
    yesterday.setDate(yesterday.getDate() - 10)

    // const date_start = yesterday.toISOString()
    // const date_end = today.toISOString()

    date_start = '2020-06-06'
    date_end = '2020-06-07'

    const params = {
        query: query_str,
        date_start: date_start,
        date_end: date_end
    }

    Object.keys(params).forEach(key => url.searchParams.append(key, params[key]))

    fetch(url)
      .then(function(response){
          return response.json()
      })
      .then(function(data){
          console.log(data)
      })
}