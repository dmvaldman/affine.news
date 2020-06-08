import psycopg2

db_user = 'affine'
db_pass = '1D2u2r3a3c3k4'
db_name = 'affine'
cloud_sql_connection_name = 'affine-news:us-central1:affine'

# local
conn = psycopg2.connect(database="affine", user="affine", password="1D2u2r3a3c3k4", host="127.0.0.1", port="5432")

# Remote
# conn = psycopg2.connect(database="affine", user="affine", password="1D2u2r3a3c3k4", host="/cloudsql/affine-news:us-central1:affine")

