export default async function handler(req,res){
  try{
    const ENABLE=String(process.env.ENABLE_AI||'false').toLowerCase()==='true'
    const HF=process.env.HF_TOKEN||''
    const MODEL=process.env.HF_MODEL||'Qwen/Qwen2.5-1.5B-Instruct'
    if(!ENABLE||!HF){ return res.status(200).json({disabled:true}) }
    const body=await readJson(req)
    const ingredients=Array.isArray(body.ingredients)?body.ingredients.map(x=>String(x||'').trim().toLowerCase()).filter(Boolean):[]
    const expiries=Array.isArray(body.expiries)?body.expiries.map(x=>String(x||'').trim()):[]
    const today=new Date().toISOString().slice(0,10)
    const valid=[]
    for(let i=0;i<ingredients.length;i++){
      const n=ingredients[i]
      const e=expiries[i]||''
      if(!e || e>=today) valid.push(n)
    }
    if(valid.length===0){
      return res.status(200).json({ok:true,text:'All ingredients are outdated or missing. Update dates to get AI suggestions.'})
    }
    const extras=['salt','pepper','water','oil','butter']
    const prompt=`You are a cooking assistant. Using only these ingredients: ${valid.join(', ')} plus pantry basics (${extras.join(', ')}), propose 3 concise recipe ideas with short steps. Do not use expired or any other ingredients. Return plain text bullets.`
    const r=await fetch(`https://api-inference.huggingface.co/models/${encodeURIComponent(MODEL)}`,{
      method:'POST',
      headers:{'Authorization':`Bearer ${HF}`,'Content-Type':'application/json'},
      body:JSON.stringify({inputs:prompt,parameters:{max_new_tokens:220,temperature:0.7}})
    })
    if(!r.ok){
      const t=await r.text()
      return res.status(200).json({ok:false,error:'Model error'})
    }
    const out=await r.json()
    const text=Array.isArray(out)&&out[0]&&out[0].generated_text?String(out[0].generated_text): (out.generated_text||'')
    return res.status(200).json({ok:true,text:text||'No result.'})
  }catch(e){
    return res.status(200).json({ok:false,error:'Unexpected error'})
  }
}
function readJson(req){
  return new Promise((resolve,reject)=>{
    let d='';req.on('data',c=>d+=c);req.on('end',()=>{try{resolve(JSON.parse(d||'{}'))}catch(_){resolve({})}})
  })
}
