/* Fail-closed investor-readiness disclosure, never an investment recommendation. */
(()=>{
 'use strict';
 const app=document.getElementById('app');
 if(!app)return;
 let manifest=null,scheduled=false;
 const escapeHtml=x=>String(x??'').replace(/[&<>"']/g,c=>({
   '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 function draw(){
  scheduled=false;
  let banner=app.querySelector('#investor-readiness-banner');
  if(!banner){
   banner=document.createElement('section');
   banner.id='investor-readiness-banner';
   banner.className='investor-readiness-banner';
   banner.setAttribute('role','status');
   banner.setAttribute('aria-live','polite');
   app.prepend(banner);
  }
  const passed=manifest?.investor_ready===true;
  const heading=passed?'Automatiske datakontroller bestått':'KONTROLLUTGAVE · IKKE GODKJENT FOR INVESTORBRUK';
  const period=manifest?.reference_quarter||'siste tilgjengelige kvartal';
  const incomplete=(manifest?.companies||[]).filter(x=>x.status!=='source_located_quarter');
  const description=!manifest?'Datakvalitet og kildekontroll kan ikke bekreftes.':passed
    ?'Automatiske kontroller er bestått for '+period+'. Faglig godkjenning kreves fortsatt.'
    :'Datagrunnlaget for '+period+' er ikke fullt verifisert eller automatisert. '+
      (incomplete.length?incomplete.length+' av 7 selskaper mangler komplette rapporterte nøkkeltall. ':'')+
      'Manglende tall estimeres ikke.';
  const html='<strong>'+escapeHtml(heading)+'</strong><span>'+escapeHtml(description)+'</span>'+
    (manifest?'<small>Kvalitetsstatus '+escapeHtml(manifest.as_of)+' · '+
    (manifest.market_data_fresh?'Forsinkede kurser/nyheter datokontrollert':'Kontroller datoer for kurser og nyheter')+'</small>':'');
  banner.classList.toggle('is-ready',passed);
  if(banner.innerHTML!==html)banner.innerHTML=html;
 }
 function schedule(){if(!scheduled){scheduled=true;queueMicrotask(draw);}}
 new MutationObserver(schedule).observe(app,{childList:true});
 schedule();
 async function refresh(){
  try{
   const res=await fetch('data/investor_readiness.json?t='+Date.now(),{cache:'no-store'});
   if(!res.ok)throw Error('HTTP '+res.status);
   const data=await res.json();
   if(data?.schema_version!==1||typeof data.investor_ready!=='boolean'||
      !Array.isArray(data.companies))throw Error('Invalid readiness manifest');
   manifest=data;
  }catch(error){
   manifest=null;
   console.warn('Investor readiness unavailable:',error);
  }
  schedule();
 }
 window.FBInvestorReadiness={refresh,get report(){return manifest;}};
 refresh();
 setInterval(refresh,300000);
})();