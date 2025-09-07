import { Client } from 'pg'

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    res.status(405).json({ error: 'Method not allowed' })
    return
  }

  const { query, date_start, date_end } = req.query
  if (!query || !date_start || !date_end) {
    res.status(400).json({ error: 'Missing params: query, date_start, date_end' })
    return
  }

  const client = new Client({ connectionString: process.env.DATABASE_URL })
  await client.connect()
  try {
    const sql = `
        SELECT
          date,
          iso,
          total,
          CAST(
            avg(total)
                OVER (
                    PARTITION BY iso
                    ORDER BY date ROWS BETWEEN 3 PRECEDING AND 3 FOLLOWING
                )
            as FLOAT) as rolling
        FROM (
          SELECT
            DATE(a.publish_at) as date,
            p.iso as iso,
            count(*) as total
          FROM article a
          JOIN paper p on a.paper_uuid = p.uuid
          WHERE DATE(a.publish_at) >= DATE($1)
          AND DATE(a.publish_at) <= DATE($2)
          AND LOWER(a.title_translated) LIKE $3
          GROUP BY 1, 2
        ) foo
        ORDER BY 1
    `
    const params = [String(date_start), String(date_end), '%' + String(query).toLowerCase() + '%']
    const { rows } = await client.query(sql, params)

    const obj = {}
    for (const r of rows) {
      const iso = r.iso
      if (!obj[iso]) obj[iso] = []
      obj[iso].push(r)
    }
    res.status(200).json(obj)
  } catch (e) {
    console.error(e)
    res.status(500).json({ error: 'Internal error' })
  } finally {
    await client.end()
  }
}
