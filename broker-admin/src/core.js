/** Pure business rules shared by the private broker Worker and tests. */
export const COMPANIES=Object.freeze(['Fremtind','Gjensidige','Tryg','Sampo','Frende','Protector','Storebrand']);
export const QUARTER=/^Q[1-4] 20\d{2}$/;
export const MAX_PDF_BYTES=10*1024*1024;
export const MAX_REPORTS_PER_FOLDER=20;
export const SUMMARY_FIELDS=Object.freeze(['reaction','drivers','outlook']);

export function assertFolder(company,quarter){
  if(!COMPANIES.includes(company)||typeof quarter!=='string'||!QUARTER.test(quarter))
    throw new TypeError('Ugyldig selskap eller kvartal');
  return {company,quarter};
}
export function periodSort(a,b){
  return Number(a.slice(3))*4+Number(a[1])-(Number(b.slice(3))*4+Number(b[1]));
}
export function periodsFromFeed(feed){
  const result=new Set();
  for(const row of Array.isArray(feed?.observations)?feed.observations:[]){
    if(row?.scope!=='group'||row.period_type!=='quarter')continue;
    const year=row.year,quarter=row.quarter;
    if(!Number.isInteger(year)||year<2024||year>2099||![1,2,3,4].includes(quarter))continue;
    result.add('Q'+quarter+' '+year);
  }
  return [...result].sort(periodSort);
}
export function normalizedSummary(input){
  if(!input||typeof input!=='object')throw new TypeError('Sammendrag mangler');
  const out={};
  for(const key of SUMMARY_FIELDS){
    if(typeof input[key]!=='string')throw new TypeError('Sammendragsfeltet '+key+' må være tekst');
    const value=input[key].trim().replace(/\r\n/g,'\n');
    if(value.length>2400)throw new TypeError('Sammendraget er for langt');
    out[key]=value;
  }
  if(out.reaction.length<30)throw new TypeError('Resultatreaksjon må inneholde minst 30 tegn');
  return out;
}
export function mergePublicFeed(current,company,quarter,summary,at){
  assertFolder(company,quarter);
  const values=normalizedSummary(summary);
  if(!current||current.schema_version!==1||!Array.isArray(current.entries))
    throw new TypeError('Ugyldig eksisterende offentlig datafil');
  const entries=[];
  for(const row of current.entries){
    if(!row||!COMPANIES.includes(row.company)||!QUARTER.test(row.quarter))throw new TypeError('Ugyldig offentlig oppføring');
    if(row.company===company&&row.quarter===quarter)continue;
    entries.push(row);
  }
  entries.push({company,quarter,...values,updated_at:at});
  entries.sort((a,b)=>periodSort(a.quarter,b.quarter)||a.company.localeCompare(b.company,'nb'));
  return {schema_version:1,entries};
}
export function outputText(result){
  if(result?.status!=='completed')throw Error('AI-behandling er ikke fullført');
  const messages=Array.isArray(result.output)?result.output:[];
  for(const message of messages){
    if(message?.type!=='message')continue;
    for(const part of message.content||[]){
      if(part.type==='output_text'&&typeof part.text==='string')return part.text;
    }
  }
  throw Error('AI svarte uten et sammendrag');
}
export function decodeAiSummary(result){
  let parsed;
  try{parsed=JSON.parse(outputText(result));}catch{throw Error('AI returnerte ikke gyldig JSON');}
  return normalizedSummary(parsed);
}
export function textSchema(){
  return {type:'object',additionalProperties:false,required:[...SUMMARY_FIELDS],
    properties:Object.fromEntries(SUMMARY_FIELDS.map(field=>[field,{type:'string'}]))};
}
export function safeFileName(input){
  if(typeof input!=='string'||input.length>180)throw new TypeError('Ugyldig PDF-filnavn');
  const name=input.replace(/[/\\\0-\x1f]/g,'').trim();
  if(!/\.pdf$/i.test(name)||name.length<5)throw new TypeError('Bare PDF er tillatt');
  return name;
}
export function publicContainsPrivateData(value){
  const s=JSON.stringify(value);
  return /"pdf"|"filename"|"r2_key"|"analysis"|"source_file"/i.test(s);
}
