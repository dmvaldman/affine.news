import { Client } from 'pg'

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    res.status(405).json({ error: 'Method not allowed' })
    return
  }

  const { date_start, date_end } = req.query;
  if (!date_start || !date_end) {
    res.status(400).json({ error: 'Missing params: date_start, date_end' })
    return
  }

  const client = new Client({ connectionString: process.env.DATABASE_URL })
  await client.connect()
  try {
    const sql = `
        SELECT DISTINCT p.iso, p.url
        FROM paper p
        JOIN article a ON p.uuid = a.paper_uuid
        WHERE a.publish_at >= $1 AND DATE(a.publish_at) <= $2
    `;
    const { rows } = await client.query(sql, [date_start, date_end]);

    const papersByCountry = {}
    for (const r of rows) {
      const iso = r.iso
      if (!papersByCountry[iso]) papersByCountry[iso] = []
      papersByCountry[iso].push(r.url)
    }
    res.status(200).json(papersByCountry)
  } catch (e) {
    console.error(e)
    res.status(500).json({ error: 'Internal error' })
  } finally {
    await client.end()
  }
}
