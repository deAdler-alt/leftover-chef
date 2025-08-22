function aiSuggest(){
  const inputs=document.querySelectorAll('input[name="ingredient"]')
  const ingredients=[]
  inputs.forEach(i=>{const v=(i.value||'').trim();if(v)ingredients.push(v)})
  const btn=document.getElementById('ai-btn')
  const out=document.getElementById('ai-out')
  btn.disabled=true
  out.innerText='Loading...'
  fetch('/api/suggest-ai',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ingredients})})
    .then(r=>r.json())
    .then(d=>{
      if(d&&d.disabled){out.innerText='AI is disabled.'}
      else if(d&&d.ok&&d.text){out.innerText=d.text}
      else{out.innerText='No result.'}
    })
    .catch(()=>{out.innerText='Error.'})
    .finally(()=>{btn.disabled=false})
}

