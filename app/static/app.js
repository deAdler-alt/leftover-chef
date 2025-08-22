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
      if(d&&d.disabled){out.innerText='AI is disabled.'}
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
