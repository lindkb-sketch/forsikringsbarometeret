/* Proprietary broker PDFs remain only in administrator's own browser.
   The public feed contains reviewed summaries, never PDF bytes or filenames. */
(()=>{
'use strict';
const NAMES=['Fremtind','Gjensidige','Tryg','Sampo','Frende','Protector','Storebrand'];
const QUARTER=/^Q[1-4] 20\d{2}$/;
const escapeHTML=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const PRIVATE_DB='forsikringsbarometeret-broker-v1';
const STORAGE=['folders','private_pdfs','drafts'];
const ADMIN=new URLSearchParams(location.search).get('admin')==='1';
let feed={schema_version:1,entries:[]},quarters=[],dialog=null,dbPromise=null;
let company='Fremtind',quarter='',renderKey='',renderElement=null;
const order=p=>Number(p.slice(3))*4+Number(p[1]);
const currentCompany=()=>typeof profitabilityCompany!=='undefined'&&NAMES.includes(profitabilityCompany)?profitabilityCompany:'Fremtind';
const currentQuarter=()=>{
 const p=window.FBActivePeriod;
 if(p&&Number.isInteger(p.year)&&Number.isInteger(p.quarter))return 'Q'+p.quarter+' '+p.year;
 return QUARTER.test(p?.label||'')?p.label:(quarters.at(-1)||'');
};
function valid(raw){
 return {schema_version:1,entries:(Array.isArray(raw?.entries)?raw.entries:[]).filter(e=>
 e&&NAMES.includes(e.company)&&QUARTER.test(e.quarter)&&
 ['reaction','drivers','outlook'].every(k=>typeof e[k]==='string'&&e[k].length<=2400)&&e.reaction.trim())};
}
function render(){
 const panel=document.getElementById('broker-commentary-panel');if(!panel)return;
 const c=currentCompany(),q=currentQuarter(),entry=feed.entries.find(e=>e.company===c&&e.quarter===q);
 const html=entry?'<div class="broker-summary-head"><h2>Meglerhusenes vurderinger</h2><p>'+escapeHTML(c)+' · '+escapeHTML(q)+'</p></div>'+
 '<div class="broker-summary-grid"><div><h3>Reaksjon på resultatet</h3><p>'+escapeHTML(entry.reaction)+'</p></div>'+
 (entry.drivers?'<div><h3>Viktigste forhold</h3><p>'+escapeHTML(entry.drivers)+'</p></div>':'')+
 (entry.outlook?'<div><h3>Forventninger fremover</h3><p>'+escapeHTML(entry.outlook)+'</p></div>':'')+'</div>'+
 '<p class="broker-summary-note">Sammenfatning av meglerhusenes vurderinger. Ikke en investeringsanbefaling.</p>':'';
 const key=c+'/'+q+'/'+html;if(renderKey===key&&renderElement===panel)return;
 renderKey=key;renderElement=panel;panel.hidden=!entry;panel.innerHTML=html;
}
async function loadPublic(){
 try{const r=await fetch('data/broker_commentary.json?ts='+Date.now(),{cache:'no-store'});
 if(!r.ok)throw Error('HTTP '+r.status);feed=valid(await r.json());render();}
 catch(e){console.warn('Meglerkommentarer kunne ikke hentes',e);}
}
function openDB(){if(!dbPromise)dbPromise=new Promise((resolve,reject)=>{
 const request=indexedDB.open(PRIVATE_DB,1);
 request.onupgradeneeded=()=>{for(const name of STORAGE)request.result.createObjectStore(name,{keyPath:'id'});};
 request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);
});return dbPromise;}
async function databaseRequest(store,method,arg){
 const db=await openDB();return new Promise((resolve,reject)=>{
 const req=db.transaction(store,method==='get'||method==='getAll'?'readonly':'readwrite')
 .objectStore(store)[method](...(arg===undefined?[]:[arg]));
 req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);
 });
}
const get=(s,k)=>databaseRequest(s,'get',k),put=(s,row)=>databaseRequest(s,'put',row),
 all=s=>databaseRequest(s,'getAll'),del=(s,k)=>databaseRequest(s,'delete',k);
async function refreshQuarters(){
 const found=new Set(feed.entries.map(e=>e.quarter));
 try{
 const r=await fetch('data/verified_financial_feed.json?ts='+Date.now(),{cache:'no-store'});
 if(!r.ok)throw Error('HTTP '+r.status);
 for(const x of (await r.json()).observations||[]){
 if(x.scope==='group'&&x.period_type==='quarter'&&Number.isInteger(x.year)&&Number.isInteger(x.quarter)){
 const q='Q'+x.quarter+' '+x.year;if(QUARTER.test(q))found.add(q);
 }}}
 catch(e){console.warn('Kunne ikke hente nye kvartaler',e);}
 quarters=[...found].filter(q=>QUARTER.test(q)).sort((a,b)=>order(a)-order(b));
 if(!quarters.length)quarters=['Q3 2026'];
 // Local virtual folders appear as soon as new verified quarters are loaded.
 for(const q of quarters)await put('folders',{id:q,createdFrom:'verified_financial_feed'});
}
const id=()=>quarter+'/'+company;
const status=(message,error=false)=>{const el=dialog?.querySelector('#broker-admin-status');if(el){
 el.textContent=message;el.classList.toggle('error',error);}};
function formValues(){return Object.fromEntries(['reaction','drivers','outlook'].map(k=>[k,dialog.querySelector('#broker-'+k).value.trim()]));}
async function saveDraft(){
 await put('drafts',{id:id(),quarter,company,...formValues(),saved_at:new Date().toISOString()});
}
async function selectFolder(){
 quarter=dialog.querySelector('#broker-quarter').value;company=dialog.querySelector('#broker-company').value;
 const draft=await get('drafts',id());const published=feed.entries.find(e=>e.quarter===quarter&&e.company===company);
 for(const key of ['reaction','drivers','outlook'])
 dialog.querySelector('#broker-'+key).value=draft?.[key]||published?.[key]||'';
 dialog.querySelector('#broker-folder-label').textContent='Privat kvartalsmappe: '+quarter.replace(' ','/')+' / '+company;
 await listPrivate();
 status('PDF-er forblir bare i denne nettleseren. Bare godkjente tekstfelt kan eksporteres til nettstedet.');
}
async function listPrivate(){
 const files=(await all('private_pdfs')).filter(x=>x.quarter===quarter&&x.company===company);
 const parent=dialog.querySelector('#broker-private-list');parent.replaceChildren();
 if(!files.length){parent.textContent='Ingen lokale PDF-er i denne mappen.';return;}
 for(const f of files){
 const row=document.createElement('div');row.className='broker-private-row';
 const name=document.createElement('span');name.textContent=f.house+' · '+f.filename+' ('+(f.size/1048576).toFixed(1)+' MB)';
 const remove=document.createElement('button');remove.type='button';remove.textContent='Slett';
 remove.onclick=async()=>{if(!confirm('Slette denne PDF-en fra nettleseren?'))return;await del('private_pdfs',f.id);await listPrivate();};
 row.append(name,remove);parent.append(row);
 }
}
async function upload(files){
 const house=dialog.querySelector('#broker-house').value.trim();
 if(!house||house.length>100){status('Skriv navnet på meglerhuset først.',true);return;}
 const old=(await all('private_pdfs')).filter(x=>x.quarter===quarter&&x.company===company);
 if(old.length+files.length>30){status('Maksimum 30 PDF-er per selskap og kvartal.',true);return;}
 let saved=0;
 for(const file of files){
 if(!/\.pdf$/i.test(file.name)||file.size>15*1048576||file.size<8){status('Ugyldig PDF eller over 15 MB.',true);continue;}
 const magic=new TextDecoder().decode(await file.slice(0,5).arrayBuffer());
 if(magic!=='%PDF-'){status('Filen er ikke en gyldig PDF.',true);continue;}
 await put('private_pdfs',{id:id()+'/'+crypto.randomUUID(),company,quarter,house,
 filename:file.name,size:file.size,storedAt:new Date().toISOString(),pdf:file});
 saved++;
 }
 await listPrivate();
 status(saved+' PDF-fil(er) lagret lokalt. Del dem bare med ChatGPT dersom meglerhusets vilkår tillater det; ellers fyll inn kontrollert sammendrag manuelt.');
}
function copyPrompt(){
 const prompt='Les de vedlagte meglerhusenes PDF-kommentarer om '+company+' '+quarter+'. Lag et nøkternt samlet norsk sammendrag i tre korte avsnitt: (1) reaksjon på kvartalsresultatet sammenlignet med forventninger, (2) viktigste drivere og eventuell uenighet, (3) estimatendringer, utsikter og risiko. Skill bekreftede fakta fra prognoser, ikke dikt opp tall, kursmål eller enighet. Merk tydelig hvis fremtidsutsikter ikke omtales. Maks 80 ord per del. Sammendraget skal kunne publiseres UTEN original-PDF-ene eller filnavn.';
 navigator.clipboard?.writeText(prompt).then(()=>status('Analyseinstruksen er kopiert. Legg PDF-ene ved i ChatGPT og lim det godkjente resultatet inn nedenfor.')).catch(()=>status(prompt));
}
async function exportSummary(){
 const value=formValues();if(value.reaction.length<30){status('Skriv et sammendrag på minst 30 tegn om resultatreaksjonen.',true);return;}
 if(Object.values(value).some(v=>v.length>2400)){status('Maksimum 2400 tegn per sammendragsfelt.',true);return;}
 const entries=feed.entries.filter(x=>!(x.company===company&&x.quarter===quarter));
 entries.push({company,quarter,...value,updated_at:new Date().toISOString()});
 entries.sort((a,b)=>order(a.quarter)-order(b.quarter)||a.company.localeCompare(b.company));
 const contents=JSON.stringify({schema_version:1,entries},null,2)+'\n';
 const url=URL.createObjectURL(new Blob([contents],{type:'application/json'}));
 const a=document.createElement('a');a.href=url;a.download='broker_commentary.json';a.click();
 setTimeout(()=>URL.revokeObjectURL(url),3000);feed={schema_version:1,entries};await saveDraft();render();
 status('Kun sammendraget er lastet ned. Publiser filen som data/broker_commentary.json i GitHub; ingen PDF-er eller PDF-filnavn følger med.');
}
function createDialog(){
 dialog=document.createElement('dialog');dialog.id='broker-admin-dialog';
 dialog.innerHTML='<div class="broker-admin-wrap"><div class="broker-admin-head"><div><small>LOKAL ADMINISTRASJON</small><h2>Meglerkommentarer per kvartal</h2><p>Private PDF-mapper og publiserbare sammendrag.</p></div><button type="button" id="broker-close">Lukk ×</button></div><div class="broker-admin-controls"><label>Kvartal<select id="broker-quarter"></select></label><label>Selskap<select id="broker-company"></select></label><label>Meglerhus<input type="text" id="broker-house" maxlength="100" placeholder="Navn på meglerhus"></label></div><strong id="broker-folder-label"></strong><label class="broker-upload">Velg PDF-er<input id="broker-pdfs" type="file" accept=".pdf,application/pdf" multiple></label><div id="broker-private-list"></div><p class="broker-private-note">PDF-er lagres KUN i denne nettleserens private IndexedDB. Ingen PDF-er, filnavn eller private mapper publiseres. Dette er ikke serverautentisering; bruk ikke delt PC, og ta egen sikkerhetskopi.</p><div class="broker-admin-actions"><button type="button" id="broker-prompt">Kopier instruks for ChatGPT</button></div><p class="broker-private-note">Automatisk AI-oppsummering direkte på nettsiden krever en sikker AI-backend. Meglerhusrapporter kan være konfidensielle og opphavsrettslig beskyttet. Ikke del dem med ChatGPT eller andre AI-tjenester uten tillatelse. Uten en godkjent sikker AI-løsning kan du fylle inn et kontrollert sammendrag manuelt.</p><div class="broker-admin-fields"><label>Reaksjon på resultatet<textarea id="broker-reaction" maxlength="2400" rows="4"></textarea></label><label>Viktigste forhold og ulike syn<textarea id="broker-drivers" maxlength="2400" rows="3"></textarea></label><label>Forventninger videre<textarea id="broker-outlook" maxlength="2400" rows="3"></textarea></label></div><div class="broker-admin-actions"><button type="button" id="broker-save">Lagre utkast lokalt</button><button type="button" class="broker-primary" id="broker-export">Last ned offentlig sammendrag</button></div><p id="broker-admin-status" role="status" aria-live="polite"></p></div>';
 document.body.append(dialog);
 const q=dialog.querySelector('#broker-quarter'),c=dialog.querySelector('#broker-company');
 for(const p of quarters.slice().reverse()){const o=document.createElement('option');o.value=p;o.textContent=p;q.append(o);}
 for(const name of NAMES){const o=document.createElement('option');o.value=name;o.textContent=name==='Sampo'?'Sampo / If':name;c.append(o);}
 q.onchange=selectFolder;c.onchange=selectFolder;
 dialog.querySelector('#broker-close').onclick=()=>dialog.close();
 dialog.querySelector('#broker-pdfs').onchange=e=>{upload([...e.target.files]);e.target.value='';};
 dialog.querySelector('#broker-save').onclick=()=>saveDraft().then(()=>status('Utkast lagret lokalt, ikke publisert.'));
 dialog.querySelector('#broker-prompt').onclick=copyPrompt;
 dialog.querySelector('#broker-export').onclick=exportSummary;
}
async function openAdmin(){
 if(!ADMIN)return;
 try{
 await refreshQuarters();if(!dialog)createDialog();
 const q=dialog.querySelector('#broker-quarter');
 const known=new Set([...q.options].map(o=>o.value));
 for(const p of quarters.slice().reverse()){if(!known.has(p)){const o=document.createElement('option');o.value=p;o.textContent=p;q.append(o);}}
 q.value=quarters.includes(currentQuarter())?currentQuarter():quarters.at(-1);
 dialog.querySelector('#broker-company').value=currentCompany();
 await selectFolder();dialog.showModal();
 }catch(e){console.error(e);alert('Lokalt PDF-arkiv kunne ikke åpnes: '+e.message);}
}
function initAdmin(){
 if(!ADMIN)return;
 const aside=document.querySelector('aside');if(!aside||document.getElementById('broker-admin-entry'))return;
 const b=document.createElement('button');b.id='broker-admin-entry';
 b.textContent='⚙ Meglerkommentarer (privat)';b.onclick=openAdmin;aside.append(b);
}
const observer=new MutationObserver(()=>{render();initAdmin();});
window.addEventListener('DOMContentLoaded',()=>{
 const app=document.getElementById('app');if(app)observer.observe(app,{subtree:true,childList:true});
 initAdmin();loadPublic();render();if(ADMIN)refreshQuarters().catch(console.warn);
 setInterval(loadPublic,300000);
});
window.FBBrokerCommentary={render,openAdmin};
})();