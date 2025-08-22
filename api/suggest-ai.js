const extras = ['salt','pepper','water','oil','butter','flour','sugar','vinegar','soy sauce']

function readJson(req){
  return new Promise((resolve)=>{let d='';req.on('data',c=>d+=c);req.on('end',()=>{try{resolve(JSON.parse(d||'{}'))}catch(_){resolve({})}})})
}

module.exports = async (req,res)=>{
  try{
    const ENABLE=String(process.env.ENABLE_AI||'false').toLowerCase()==='true'
    if(!ENABLE) return res.status(200).json({disabled:true})
    const body=await readJson(req)
    const ings=Array.isArray(body.ingredients)?body.ingredients.map(x=>String(x||'').trim().toLowerCase()).filter(Boolean):[]
    const exps=Array.isArray(body.expiries)?body.expiries.map(x=>String(x||'').trim()):[]
    const today=new Date().toISOString().slice(0,10)
    const valid=[]
    for(let i=0;i<ings.length;i++){ const e=exps[i]||''; if(!e||e>=today) valid.push(ings[i]) }
    if(valid.length===0) return res.status(200).json({ok:true,text:'All ingredients are outdated or missing. Update dates to get AI suggestions.'})
    const text =
`• Quick Ideas
  - Combine ${valid[0]||'your main ingredient'} with pantry basics
  - Sear in oil, season with salt and pepper
  - Add acidity with vinegar or soy sauce
• Pantry Pasta
  - Boil pasta
  - Sizzle garlic in oil
  - Toss with ${valid.join(', ') || 'your veg'} and a splash of cooking water
• Skillet Toss
  - Chop ingredients evenly
  - High heat sauté
  - Finish with butter and black pepper`
    return res.status(200).json({ok:true,text})
  }catch(e){
    return res.status(200).json({ok:false,error:'Unexpected error'})
  }
}
