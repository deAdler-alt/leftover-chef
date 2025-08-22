const { parse } = require('node-html-parser')

const MAX_CHARS = 5000

function readJson(req){
  return new Promise((resolve)=>{let d='';req.on('data',c=>d+=c);req.on('end',()=>{try{resolve(JSON.parse(d||'{}'))}catch(_){resolve({})}})})
}

function getUrlParam(req){
  try{
    const base='https://dummy.local'
    const u=new URL(req.url,base)
    return u.searchParams.get('url')||''
  }catch{ return '' }
}

async function fetchHtml(targetUrl){
  try{
    const r=await fetch(targetUrl,{method:'GET',headers:{
      'user-agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      'accept':'text/html,application/xhtml+xml'
    }})
    if(!r.ok) return null
    const ct=r.headers.get('content-type')||''
    if(!ct.includes('text/html')){}
    return await r.text()
  }catch{ return null }
}

function textFromNode(node){
  return (node?.innerText||'').replace(/\s+/g,' ').trim()
}

function collectReadableText(container){
  if(!container) return ''
  const blocks=[]
  const keep=new Set(['p','li','blockquote','pre','code','h1','h2','h3'])
  container.querySelectorAll('*').forEach(el=>{
    const tag=el.tagName?.toLowerCase?.()||''
    if(keep.has(tag)){
      const raw=(el.innerText||'').replace(/\s+\n/g,'\n').replace(/\n\s+/g,'\n').trim()
      if(raw&&raw.length>=30){ blocks.push(raw) }
    }
  })
  if(blocks.length===0){
    const raw=(container.innerText||'').replace(/\s+\n/g,'\n').replace(/\n\s+/g,'\n').trim()
    return raw
  }
  return blocks.join('\n\n')
}

function extractArticle(html){
  const root=parse(html,{lowerCaseTagName:false,script:true,style:true,pre:true,comment:false})
  const title=(root.querySelector('title')?.text||'').trim()
  const noisy=['script','style','noscript','svg','canvas','form','nav','footer','header','aside','iframe','ads','.ads','.advert','.promo']
  noisy.forEach(sel=>root.querySelectorAll(sel).forEach(n=>n.remove()))
  const candidates=['article','main','[role="main"]','.content','.post-content','.entry-content','#content','#main','.article','.post','.story']
  let best=null, bestScore=0
  for(const sel of candidates){
    root.querySelectorAll(sel).forEach(node=>{
      const t=textFromNode(node)
      const score=t.length
      if(score>bestScore){ bestScore=score; best=node }
    })
    if(bestScore>800) break
  }
  const target=best||root.querySelector('body')||root
  const text=collectReadableText(target)
  return { title, text }
}

module.exports = async (req,res)=>{
  try{
    const url=getUrlParam(req)
    if(!url||!/^https?:\/\//i.test(url)) return res.status(200).json({ ok:false, error:'Invalid or missing url param' })
    const html=await fetchHtml(url)
    if(!html) return res.status(200).json({ ok:false, error:'Failed to fetch page' })
    const { title, text }=extractArticle(html)
    if(!text||text.trim().length<50) return res.status(200).json({ ok:false, error:'Could not extract readable text' })
    const trimmed=text.trim().replace(/\n{3,}/g,'\n\n').slice(0,MAX_CHARS)
    return res.status(200).json({ ok:true, title:(title||'').trim().slice(0,160), text:trimmed })
  }catch(e){
    return res.status(200).json({ ok:false, error:'Unexpected error' })
  }
}
