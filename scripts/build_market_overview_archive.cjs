#!/usr/bin/env node
'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {makeView,viewKey}=require('./market_overview.js');
const root=path.resolve(__dirname,'..','data');
const keys=['group','norway'].flatMap(s=>['all','pm','bm'].flatMap(m=>['quarter','ytd'].map(p=>viewKey(s,m,p))));
const label=p=>p?'Q'+p.quarter+' '+p.year:null;
const serial=s=>{const m=/^Q([1-4]) (\d{4})$/.exec(s||'');if(!m)throw Error('Invalid market quarter: '+s);return Number(m[2])*4+Number(m[1])-1;};
const clone=x=>JSON.parse(JSON.stringify(x));
const digest=x=>crypto.createHash('sha256').update(JSON.stringify(x)).digest('hex');
function validate(a){
 if(a.schema_version!==1||!a.periods||typeof a.periods!=='object')throw Error('Invalid archive schema');
 if(!a.active_period){if(Object.keys(a.periods).length)throw Error('Archive has no active period');return;}
 const latest=serial(a.active_period);
 if(!a.periods[a.active_period])throw Error('Missing active market period');
 for(const [period,item] of Object.entries(a.periods)){
  if(serial(period)>latest||item.locked!==(period!==a.active_period)||Object.keys(item.views||{}).length!==keys.length||!keys.every(k=>item.views[k]&&label(item.views[k].model?.period)===period&&item.views[k].model.mode===k.split('/')[2]&&Array.isArray(item.views[k].comments)&&Array.isArray(item.views[k].sources)))throw Error('Inconsistent archive period '+period);
  if(item.digest!==digest(item.views))throw Error('Archive content changed for '+period);
 }
}
function build(inputs,previous={schema_version:1,active_period:null,periods:{}},{strict=false}={}){
 validate(previous);
 const {feed,comparison,fx,segments,context,editorial}=inputs;
 const first=makeView(feed,comparison,fx,segments,context,editorial,'group','all','quarter');
 const period=label(first.model.period);
 if(!period){if(previous.active_period)return clone(previous);throw Error('No verified current quarter');}
 const old=previous.active_period;
 if(old&&serial(period)<serial(old))throw Error('Refusing to rewind market archive');
 if(old&&serial(period)>serial(old)+1)throw Error('Refusing to skip an unarchived reporting quarter');
 const next=clone(previous);
 const views={};
 for(const k of keys){
  const [scope,market,mode]=k.split('/');
  const previousPeriod=Object.keys(previous.periods).find(p=>serial(p)===serial(period)-1);
  const priorView=mode==='quarter'&&previousPeriod?previous.periods[previousPeriod].views[k]:null;
  const view=makeView(feed,comparison,fx,segments,context,editorial,scope,market,mode,priorView);
  if(label(view.model.period)!==period)throw Error('Mixed snapshot quarters '+k);
  views[k]=clone(view);
 }
 if(strict){
  const expected={'group/all':9,'group/pm':4,'group/bm':5,'norway/all':7,'norway/pm':2,'norway/bm':3};
  for(const k of keys){
   const m=views[k].model,n=expected[k.split('/').slice(0,2).join('/')];
   if(m.eligible.length!==n||m.selected.length!==Math.min(5,n)||m.fxMissing.length)throw Error('Incomplete baseline snapshot '+k+': '+m.eligible.length+'/'+n+' eligible, '+m.selected.length+' plotted');
  }
 }
 if(old&&old!==period)next.periods[old].locked=true;
 next.active_period=period;
 next.periods[period]={locked:false,views,digest:digest(views)};
 validate(next);
 for(const [k,item] of Object.entries(previous.periods))if(item.locked&&JSON.stringify(item)!==JSON.stringify(next.periods[k]))throw Error('Historical archive rewrite '+k);
 return next;
}
function main(){
 const load=n=>JSON.parse(fs.readFileSync(path.join(root,n),'utf8'));
 const target=path.join(root,'market_overview_archive.json');
 const previous=fs.existsSync(target)?load('market_overview_archive.json'):undefined;
 const inputs={feed:load('verified_financial_feed.json'),comparison:load('nine_insurer_comparison.json'),fx:load('market_overview_fx.json'),segments:load('market_overview_segments.json'),context:load('market_overview_context.json'),editorial:load('quarterly_editorial.json')};
 const result=build(inputs,previous,{strict:process.argv.includes('--require-baseline')});
 const tmp=target+'.tmp';fs.writeFileSync(tmp,JSON.stringify(result,null,2)+'\n');fs.renameSync(tmp,target);
 console.log('MARKET_ARCHIVE_VERIFIED',result.active_period,Object.fromEntries(Object.entries(result.periods).map(([p,r])=>[p,{locked:r.locked,views:Object.keys(r.views).length,counts:Object.fromEntries(Object.entries(r.views).map(([k,v])=>[k,v.model.eligible.length]))}])));
}
if(require.main===module)main();
module.exports={build,validate,digest,keys};
