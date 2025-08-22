const { parse } = require('node-html-parser')

const MAX_CHARS = 5000

module.exports = async function (req, res) {
  try {
    const url = getUrlParam(req)
    if (!url || !/^https?:\/\//i.test(url)) {
      return res.status(200).json({ ok: false, error: 'Invalid or missing url param' })
    }

    const html = await fetchHtml(url, 10000)
    if (!html) {
      return res.status(200).json({ ok: false, error: 'Failed to fetch page' })
    }

    const { title, text } = extractArticle(html)
    if (!text || text.trim().length < 50) {
      return res.status(200).json({ ok: false, error: 'Could not extract readable text' })
    }

    const trimmed = text.trim().replace(/\n{3,}/g, '\n\n').slice(0, MAX_CHARS)
    res.setHeader('Cache-Control', 'public, s-maxage=3600, stale-while-revalidate=60')
    return res.status(200).json({ ok: true, title: (title || '').trim().slice(0, 160), text: trimmed })
  } catch (e) {
    return res.status(200).json({ ok: false, error: 'Unexpected error' })
  }
}

function getUrlParam(req) {
  try {
    const u = new URL(req.url, 'https://dummy.local')
    return u.searchParams.get('url') || ''
  } catch {
    return ''
  }
}

async function fetchHtml(targetUrl, timeoutMs = 10000) {
  try {
    const controller = new AbortController()
    const id = setTimeout(() => controller.abort(), timeoutMs)
    const r = await fetch(targetUrl, {
      method: 'GET',
      headers: {
        'user-agent': 'Mozilla/5.0',
        'accept': 'text/html,application/xhtml+xml'
      },
      signal: controller.signal
    })
    clearTimeout(id)
    if (!r.ok) return null
    const ct = r.headers.get('content-type') || ''
    if (!(ct.includes('text/html') || ct.includes('application/xhtml+xml'))) return null
    return await r.text()
  } catch {
    return null
  }
}

function extractArticle(html) {
  const root = parse(html, { lowerCaseTagName: false, script: true, style: true, pre: true, comment: false })
  const title = (root.querySelector('title')?.text || '').trim()
  const noisySelectors = ['script','style','noscript','svg','canvas','form','nav','footer','header','aside','iframe','ads','.ads','.advert','.promo']
  noisySelectors.forEach(sel => root.querySelectorAll(sel).forEach(n => n.remove()))
  const candidates = ['article','main','[role="main"]','.content','.post-content','.entry-content','#content','#main','.article','.post','.story']
  let bestNode = null, bestScore = 0
  for (const sel of candidates) {
    root.querySelectorAll(sel).forEach(node => {
      const t = (node.innerText || '').replace(/\s+/g, ' ').trim()
      if (t.length > bestScore) { bestScore = t.length; bestNode = node }
    })
    if (bestScore > 800) break
  }
  const target = bestNode || root.querySelector('body') || root
  const keep = new Set(['p','li','blockquote','pre','code','h1','h2','h3'])
  const blocks = []
  target.querySelectorAll('*').forEach(el => {
    const tag = el.tagName?.toLowerCase?.() || ''
    if (keep.has(tag)) {
      const raw = (el.innerText || '').replace(/\s+\n/g, '\n').replace(/\n\s+/g, '\n').trim()
      if (raw && raw.length >= 30) blocks.push(raw)
    }
  })
  const text = blocks.length ? blocks.join('\n\n') : (target.innerText || '').replace(/\s+\n/g, '\n').replace(/\n\s+/g, '\n').trim()
  return { title, text }
}

