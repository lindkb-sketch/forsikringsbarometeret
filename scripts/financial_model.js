
(function(){
'use strict';
const mandatory=['company','year','quarter','scope','period_type','metric','value','source_url','source_page','source_type'];
function checkObservation(r){
 const errors=[];
 for(const key of mandatory) if(r[key]===undefined||r[key]===null||r[key]==='')errors.push('Mangler '+key);
 if(r.source_type!=='official_quarterly_report')errors.push('Ugyldig kilde');
 if(!Number.isFinite(r.value))errors.push('Ugyldig verdi');
 if(r.scope==='norway' && r.source_scope==='group')errors.push('Konserntall kan ikke være Norge-tall');
 return errors;
}
function growth(current,prior){
 if(!Number.isFinite(current)||!Number.isFinite(prior)||prior<=0)return null;
 return (current/prior-1)*100;
}
function isolated(ytd,previousYtd){
 if(!Number.isFinite(ytd)||!Number.isFinite(previousYtd))return null;
 return ytd-previousYtd;
}
function audit(records){
 const errors=[];
 const index=new Map();
 for(const [i,r] of records.entries()){
  for(const e of checkObservation(r))errors.push(`Rad ${i+1}: ${e}`);
  const key=[r.company,r.year,r.quarter,r.scope,r.period_type,r.metric].join('|');
  if(index.has(key))errors.push(`Duplikat: ${key}`);
  index.set(key,r);
 }
 for(const r of records){
  if(r.metric!=='combined_ratio')continue;
  const key=m=>[r.company,r.year,r.quarter,r.scope,r.period_type,m].join('|');
  const loss=index.get(key('loss_ratio')),expense=index.get(key('expense_ratio'));
  if(loss&&expense&&Math.abs(r.value-loss.value-expense.value)>0.25)errors.push(`CR-avvik: ${r.company} ${r.year} Q${r.quarter} ${r.scope}`);
 }
 return errors;
}
window.ForsikringsbarometerData=Object.freeze({checkObservation,growth,isolated,audit});
})();
