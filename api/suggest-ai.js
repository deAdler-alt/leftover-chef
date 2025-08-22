const toList = (s) => String(s||"").split(",").map(x=>x.trim()).filter(Boolean);

const DEFAULT_MODELS = [
  "Qwen/Qwen2.5-1.5B-Instruct",
  "Qwen/Qwen2-1.5B-Instruct",
  "microsoft/Phi-4-mini-instruct",
  "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
  "Qwen/Qwen2.5-0.5B-Instruct"
];

export default async function handler(req,res){
  try{
    const ENABLE=String(process.env.ENABLE_AI||'false').toLowerCase()==='true';
    const HF=process.env.HF_TOKEN||'';
    const CANDIDATES = toList(process.env.HF_MODELS).length ? toList(process.env.HF_MODELS) : DEFAULT_MODELS;
    if(!ENABLE||!HF){ return res.status(200).json({disabled:true}) }

    const body=await readJson(req);
    const ingredients=Array.isArray(body.ingredients)?body.ingredients.map(x=>String(x||'').trim().toLowerCase()).filter(Boolean):[];
    const expiries=Array.isArray(body.expiries)?body.expiries.map(x=>String(x||'').trim()):[];
    const today=new Date().toISOString().slice(0,10);
    const valid=[];
    for(let i=0;i<ingredients.length;i++){
      const n=ingredients[i]; const e=expiries[i]||'';
      if(!e || e>=today) valid.push(n);
    }
    if(valid.length===0){
      return res.status(200).json({ok:true,text:'All ingredients are outdated or missing. Update dates to get AI suggestions.'})
    }

    const extras=['salt','pepper','water','oil','butter','flour','sugar','vinegar','soy sauce'];
    const prompt=`You are a cooking assistant. Using only these ingredients: ${valid.join(', ')} plus pantry basics (${extras.join(', ')}), propose exactly 3 concise recipe ideas. For each: a title and 3-5 short steps. Do not add other ingredients. Return plain text bullets.`;

    for(const MODEL of CANDIDATES){
      const r=await fetch(`https://api-inference.huggingface.co/models/${encodeURIComponent(MODEL)}`,{
        method:'POST',
        headers:{'Authorization':`Bearer ${HF}`,'Content-Type':'application/json'},
        body:JSON.stringify({inputs:prompt,parameters:{max_new_tokens:250,temperature:0.7,return_full_text:false}})
      });
      if(r.status===503||r.status===202) continue;
      if(r.status===429) return res.status(200).json({ok:false,error:'Rate limited, please retry.'});
      if(!r.ok) continue;
      const out=await r.json();
      const text=Array.isArray(out)?String(out[0]?.generated_text||out[0]?.summary_text||''):String(out.generated_text||out.summary_text||'');
      if(text.trim()) return res.status(200).json({ok:true,model:MODEL,text:text.trim()});
    }
    return res.status(200).json({ok:false,error:'No model responded. Try again.'});
  }catch(e){
    return res.status(200).json({ok:false,error:'Unexpected error'});
  }
}

function readJson(req){
  return new Promise((resolve)=>{let d='';req.on('data',c=>d+=c);req.on('end',()=>{try{resolve(JSON.parse(d||'{}'))}catch(_){resolve({})}})})
}
