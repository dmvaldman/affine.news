import { Client } from 'pg'

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    res.status(405).json({ error: 'Method not allowed' })
    return
  }

  const { query, date_start, date_end, country } = req.query
  if (!query || !date_start || !date_end) {
    res.status(400).json({ error: 'Missing params: query, date_start, date_end' })
    return
  }

  const client = new Client({ connectionString: process.env.DATABASE_URL })
  await client.connect()
  try {
    let sql = `SELECT p.country as country, p.ISO as iso, p.url as paper_url, p.lang as lang, a.url as article_url, a.publish_at, a.title_translated FROM article a
      JOIN paper p on p.uuid = a.paper_uuid
      WHERE a.publish_at >= $1
      AND DATE(a.publish_at) <= $2
      AND a.title_translated is not NULL
      ORDER BY a.publish_at desc`
    const params = [String(date_start), String(date_end)]
    if (country) {
      sql += ' AND p.country = $3'
      params.push(country)
    }
    const { rows } = await client.query(sql, params)

    // post-filter for CSV keywords (case-insensitive)
    const words = String(query).split(',').map(w => w.trim()).filter(Boolean)
    const matched = rows.filter(r => words.some(w => new RegExp(w, 'i').test(r.title_translated)))

    const byCountry = {}
    for (const r of matched) {
      const iso = r.iso
      if (!byCountry[iso]) byCountry[iso] = []
      byCountry[iso].push({
        article_url: r.article_url,
        title: r.title_translated,
        paper_url: r.paper_url,
        publish_at: r.publish_at,
        lang: r.lang
      })
    }
    res.status(200).json(byCountry)
  } catch (e) {
    console.error(e)
    res.status(500).json({ error: 'Internal error' })
  } finally {
    await client.end()
  }
}


