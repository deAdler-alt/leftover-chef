export default async function handler(req, res) {
  const enabled = (process.env.ENABLE_AI || 'false').toLowerCase() === 'true'
  if (!enabled) {
    return res.status(200).json({ ok: false, disabled: true, reason: 'AI disabled' })
  }
  const key = process.env.OPENROUTER_API_KEY
  const base = process.env.OPENROUTER_BASE_URL || 'https://openrouter.ai/api/v1'
  if (!key) {
    return res.status(200).json({ ok: false, disabled: true, reason: 'Missing API key' })
  }

  try {
    const body = await readBody(req)
    const { ingredients = [] } = body || {}
    const prompt = `Given this list of ingredients: ${ingredients.join(', ')}, propose 3 simple, budget-friendly recipe ideas (name only).`

    const r = await fetch(`${base}/chat/completions`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${key}`,
        'Content-Type': 'application/json',
        'HTTP-Referer': 'https://leftover-chef.vercel.app',
        'X-Title': 'LeftoverChef'
      },
      body: JSON.stringify({
        model: "meta-llama/llama-3.1-8b-instruct:free",
        messages: [
          { role: "system", content: "Be concise. Return only recipe names as a numbered list." },
          { role: "user", content: prompt }
        ],
        temperature: 0.7,
        max_tokens: 160
      })
    })

    if (!r.ok) {
      const txt = await safeText(r)
      return res.status(200).json({ ok: false, error: 'Model error', detail: txt.slice(0,500) })
    }
    const data = await r.json()
    const text = data?.choices?.[0]?.message?.content || ""
    return res.status(200).json({ ok: true, disabled: false, text })
  } catch (e) {
    console.error('suggest-ai error', e)
    return res.status(200).json({ ok: false, error: 'Unexpected error' })
  }
}

function readBody(req) {
  return new Promise((resolve) => {
    let data = ""
    req.on('data', chunk => { data += chunk })
    req.on('end', () => {
      try { resolve(JSON.parse(data || "{}")) } catch { resolve({}) }
    })
  })
}

async function safeText(r) {
  try { return await r.text() } catch { return '' }
}

