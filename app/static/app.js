let webllmEngine=null

function gatherValid(){
  const form=document.getElementById('ing-form')
  const ings=[...form.querySelectorAll('input[name="ingredient"]')].map(i=>String(i.value||'').trim().toLowerCase()).filter(Boolean)
  const exps=[...form.querySelectorAll('input[name="expiry"]')].map(i=>String(i.value||'').trim())
  const today=new Date().toISOString().slice(0,10)
  const valid=[]
  for(let i=0;i<ings.length;i++){ const e=exps[i]||''; if(!e||e>=today) valid.push(ings[i]) }
  return valid
}
function bulletBlock(title,steps){
  const lines=[`• ${title}`]
  for(const s of steps){ lines.push(`  - ${s}`) }
  return lines.join('\n')
}
function has(v,one){ return v.includes(one) }
function any(v,list){ return list.some(x=>v.includes(x)) }

function aiSuggestLocal(){
  const btn=document.getElementById('ai-local-btn')
  const out=document.getElementById('ai-out')
  setBusy(btn,true)
  try{
    const v=gatherValid()
    if(v.length===0){ out.textContent='All ingredients are outdated or missing. Update dates to get suggestions.'; return }
    const base=new Set(['salt','pepper','water','oil','butter','flour','sugar','vinegar','soy sauce'])
    const ideas=[]
    if(has(v,'eggs')||has(v,'egg')){
      const add=any(v,['cheese','onion','bell pepper'])?v.find(x=>['cheese','onion','bell pepper'].includes(x)):'herbs'
      ideas.push(bulletBlock('Herby Omelette',[
        `Whisk eggs with salt and pepper`,
        `Warm pan with a little oil or butter`,
        `Pour eggs, gently stir edges`,
        `Add ${add}`,
        `Fold and serve`
      ]))
    }
    if(any(v,['tomato','tomatoes'])&&(has(v,'eggs')||has(v,'egg'))){
      const arom=v.find(x=>['onion','garlic'].includes(x))||'chili'
      ideas.push(bulletBlock('Tomato & Egg Skillet',[
        `Soften ${arom} in oil`,
        `Add chopped tomato, simmer and season`,
        `Make small wells, crack in eggs`,
        `Cover until whites set`,
        `Finish with pepper`
      ]))
    }
    if(has(v,'rice')){
      const veg=v.find(x=>['carrot','peas','onion','garlic','spring onion'].includes(x))||'any chopped veg'
      const eggPart=(has(v,'eggs')||has(v,'egg'))?'Push rice aside and scramble an egg, then mix':'Stir-fry 1 min more'
      const soy=has(v,'soy sauce')?'soy sauce':'salt'
      ideas.push(bulletBlock('Quick Fried Rice',[
        `Heat oil, add ${veg}`,
        `Add cold cooked rice`,
        `Season with ${soy}`,
        `${eggPart}`,
        `Finish with pepper`
      ]))
    }
    if(has(v,'pasta')&&has(v,'garlic')){
      ideas.push(bulletBlock('Aglio e Olio',[
        `Cook pasta in salted water`,
        `Sizzle sliced garlic in oil until pale gold`,
        `Toss pasta with a splash of cooking water`,
        `Season with chili flakes if you have them`,
        `Black pepper to finish`
      ]))
    }
    if(has(v,'bread')&&any(v,['tomato','tomatoes'])){
      const add=v.find(x=>['cucumber','red onion','onion','basil'].includes(x))
      ideas.push(bulletBlock('Panzanella-Style Salad',[
        `Toast torn bread until crisp`,
        `Combine chopped tomato${add?` and ${add}`:''}`,
        `Dress with oil and vinegar`,
        `Toss with bread to soak juices`,
        `Season and rest 10 min`
      ]))
    }
    if(ideas.length<3&&any(v,['lettuce','cucumber','tomato','pepper','onion'])){
      const veg=v.filter(x=>['lettuce','cucumber','tomato','pepper','onion'].includes(x))
      ideas.push(bulletBlock('Zero-Waste Salad',[
        `Chop ${veg.length?veg.join(', '):'your veg'}`,
        `Add oil, vinegar, salt and pepper`,
        `Toss well`,
        `Top with toasted bread cubes if you have bread`,
        `Serve chilled`
      ]))
    }
    if(ideas.length<3&&has(v,'bread')&&has(v,'cheese')){
      ideas.push(bulletBlock('Grilled Cheese',[
        `Heat pan on medium`,
        `Assemble bread with cheese`,
        `Toast with a little butter or oil`,
        `Flip until cheese melts`,
        `Slice and serve`
      ]))
    }
    if(ideas.length===0){
      ideas.push(bulletBlock('Simple Saute',[
        `Slice your vegetables`,
        `Saute in oil, season with salt and pepper`,
        `Add a splash of vinegar or soy sauce`,
        `Serve warm`
      ]))
    }
    const top=ideas.slice(0,3)
    out.textContent=top.join('\n\n')
  }finally{
    setBusy(btn,false)
  }
}

async function aiSuggestBrowser(){
  const btn=document.getElementById('ai-browser-btn')
  const out=document.getElementById('ai-out')
  setBusy(btn,true)
  try{
    if(!('gpu' in navigator)){ aiSuggestLocal(); return }
    if(!window.webllm){ window.webllm=await import('https://esm.run/@mlc-ai/web-llm') }
    if(!webllmEngine){
      const model='Llama-3.2-1B-Instruct-q4f16_1-MLC'
      webllmEngine=await window.webllm.CreateMLCEngine(model,{initProgressCallback:(p)=>{ out.textContent=p.text||('Loading '+Math.round((p.progress||0)*100)+'%') }})
    }
    const v=gatherValid()
    if(v.length===0){ out.textContent='All ingredients are outdated or missing. Update dates to get AI suggestions.'; return }
    const extras=['salt','pepper','water','oil','butter','flour','sugar','vinegar','soy sauce']
    const prompt=`You are a cooking assistant. Using only these ingredients: ${v.join(', ')} plus pantry basics (${extras.join(', ')}), propose exactly 3 concise recipe ideas. For each: a title and 3-5 short steps. Do not add other ingredients. Return plain text bullets.`
    const messages=[{role:'system',content:'Answer in English and keep it concise.'},{role:'user',content:prompt}]
    const chunks=await webllmEngine.chat.completions.create({messages,temperature:0.7,stream:true})
    let acc=''
    for await (const ch of chunks){ acc+=ch.choices?.[0]?.delta?.content||''; out.textContent=acc }
  }catch(e){
    aiSuggestLocal()
  }finally{
    setBusy(btn,false)
  }
}

function aiSuggest(){
  const form=document.getElementById('ing-form')
  const ings=[...form.querySelectorAll('input[name="ingredient"]')].map(i=>(i.value||'').trim())
  const exps=[...form.querySelectorAll('input[name="expiry"]')].map(i=>i.value||'')
  const btn=document.getElementById('ai-btn')
  setBusy(btn,true)
  fetch('/api/suggest-ai',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ingredients:ings,expiries:exps})})
    .then(r=>r.json())
    .then(d=>{
      const out=document.getElementById('ai-out')
      if(d&&d.disabled){out.innerText='Server AI is disabled.'}
      else if(d&&d.ok&&d.text){out.innerText=d.text}
      else if(d&&d.error){out.innerText=d.error}
      else{out.innerText='No result.'}
    })
    .catch(()=>{document.getElementById('ai-out').innerText='Error.'})
    .finally(()=>setBusy(btn,false))
}

function removeRow(btn){
  const row=btn.closest('.row');if(row)row.remove();saveForm()
}
function saveForm(){
  const form=document.getElementById('ing-form')
  if(!form)return
  const fd=new FormData(form)
  fetch('/save',{method:'POST',body:fd})
}
function setBusy(el,on){
  if(!el)return
  if(on){
    el.setAttribute('aria-busy','true')
    el.disabled=true
    const s=document.createElement('span');s.className='spinner';s.setAttribute('data-spin','1')
    const t=document.createElement('span');t.textContent=el.getAttribute('data-label')||el.textContent
    el.setAttribute('data-label',el.textContent)
    el.textContent=''
    el.appendChild(s);el.appendChild(t)
  }else{
    el.removeAttribute('aria-busy')
    el.disabled=false
    const label=el.getAttribute('data-label')||''
    el.textContent=label
  }
}
document.addEventListener('submit',e=>{
  const sub=e.target && e.target.querySelector('button[type="submit"]')
  if(sub)setBusy(sub,true)
})
document.addEventListener('change',e=>{
  const t=e.target
  if(t&&(t.name==='ingredient'||t.name==='expiry')) saveForm()
})
