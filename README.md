To switch between production and development environments change `ENV='DEV'/'PROD'` in `.env` and switch the localhost and global URL in `static/js/app.js`

Run local DB proxy
```
./cloud_sql_proxy -instances=affine-news:us-central1:affine=tcp:5432 -credential_file=affine-news-97580ef473e5.json
```

Run server

```
python3 main.py
```

Open `localhost:8000` in a web browser

Query DB

```
gcloud sql connect affine --user=affine
/d affine
```

Tail logs

```
gcloud app logs tail
```

Deploy

```
gcloud app deploy
```