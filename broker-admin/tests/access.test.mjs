import test from 'node:test';
import assert from 'node:assert/strict';
import {after} from 'node:test';
import {generateKeyPair,exportJWK,SignJWT} from 'jose';
import worker from '../src/index.js';

const team='broker-test.cloudflareaccess.com';
const aud='broker-admin-test-app';
const originalFetch=globalThis.fetch;
after(()=>{globalThis.fetch=originalFetch;});
let signingKey;
async function signedToken(email){
  if(!signingKey){
    const keys=await generateKeyPair('RS256',{extractable:true});
    const publicJwk=await exportJWK(keys.publicKey);
    publicJwk.kid='mock-access-key';
    publicJwk.alg='RS256';
    publicJwk.use='sig';
    signingKey=keys.privateKey;
    globalThis.fetch=async input=>{
      const url=typeof input==='string'?input:input.url;
      if(url==='https://'+team+'/cdn-cgi/access/certs'){
        return new Response(JSON.stringify({keys:[publicJwk]}),{
          status:200,headers:{'Content-Type':'application/json'}
        });
      }
      throw Error('Network access outside fake JWKS was attempted: '+url);
    };
  }
  return new SignJWT({email})
    .setProtectedHeader({alg:'RS256',kid:'mock-access-key'})
    .setIssuer('https://'+team)
    .setAudience(aud)
    .setIssuedAt()
    .setExpirationTime('5m')
    .sign(signingKey);
}
const authEnv={ACCESS_TEAM_DOMAIN:team,ACCESS_AUD:aud,ADMIN_EMAILS:'admin@example.test'};
function request(path,{method='GET',token=null,origin=null,body=null}={}){
 const headers={};
 if(token)headers['Cf-Access-Jwt-Assertion']=token;
 if(origin)headers.Origin=origin;
 if(body!==null)headers['Content-Type']='application/json';
 return new Request('https://portal.example.test'+path,{
   method,headers,...(body!==null?{body:JSON.stringify(body)}:{})
 });
}

test('Worker fails closed if Access or allowlist is not configured',async()=>{
 const res=await worker.fetch(request('/'),{});
 assert.equal(res.status,503);
 assert.match(await res.text(),/ikke konfigurert/);
});
test('private HTML and API are unavailable without a signed Access JWT',async()=>{
 for(const path of ['/','/admin.js','/api/bootstrap','/api/reports?company=Tryg&quarter=Q3%202026']){
   const res=await worker.fetch(request(path),authEnv);
   assert.equal(res.status,401,path);
 }
});
test('valid signed Access token grants only allowlisted account access',async()=>{
 const wrong=await signedToken('someone@example.test');
 const denied=await worker.fetch(request('/admin.css',{token:wrong}),authEnv);
 assert.equal(denied.status,403);
 const admin=await signedToken('ADMIN@example.test');
 const ok=await worker.fetch(request('/admin.js',{token:admin}),authEnv);
 assert.equal(ok.status,200);
 assert.match(await ok.text(),/Godkjenn|approve/u);
 assert.equal(ok.headers.get('X-Frame-Options'),'DENY');
 assert.match(ok.headers.get('Content-Security-Policy'),/default-src 'none'/);
});
test('forged token is denied',async()=>{
 const token=await signedToken('admin@example.test');
 const parts=token.split('.');
 const sig=parts[2],mid=Math.floor(sig.length/2);
 const forged=parts[0]+'.'+parts[1]+'.'+sig.slice(0,mid)+(sig[mid]==='a'?'b':'a')+sig.slice(mid+1);
 const res=await worker.fetch(request('/',{token:forged}),authEnv);
 assert.equal(res.status,401);
});
test('cross-site POST cannot pass origin check even with valid JWT',async()=>{
 const token=await signedToken('admin@example.test');
 const denied=await worker.fetch(request('/api/publish',{
   method:'POST',token,origin:'https://other-site.test',
   body:{company:'Gjensidige',quarter:'Q3 2026',reaction:'Test result reaction text that is longer than thirty characters.',drivers:'',outlook:''}
 }),authEnv);
 assert.equal(denied.status,403);
 assert.match(await denied.text(),/opprinnelse/);
});
