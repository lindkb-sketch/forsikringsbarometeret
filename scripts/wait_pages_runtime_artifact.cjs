'use strict';
// The REST artifacts endpoint and the runtime ArtifactService can disagree
// just after an upload. deploy-pages@v4 uses the latter. Require the exact
// ID from upload-pages-artifact, visible twice via that same client.
async function waitForRuntimeArtifact({client,expectedId,name='github-pages',attempts=18,delayMs=4000,sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms)),log=console.log}) {
  if (!/^[1-9]\d*$/.test(String(expectedId))) throw new Error('Missing valid Pages upload artifact ID');
  if (!client || typeof client.listArtifacts!=='function') throw new Error('Missing Actions runtime artifact client');
  let consecutive=0;
  for(let i=1;i<=attempts;i++){
    let response;
    try{
      response=await client.listArtifacts();
    }catch(error){
      // Transient read failures are safe to retry. Never retry deployment
      // creation itself or print runtime-token-bearing error payloads.
      consecutive=0;
      log('PAGES_RUNTIME_LIST_UNAVAILABLE attempt '+i+'/'+attempts);
      if(i<attempts)await sleep(delayMs);
      continue;
    }
    if(!Array.isArray(response?.artifacts))throw new Error('Invalid runtime artifact list response');
    const matches=response.artifacts.filter(item=>item.name===name);
    if(matches.length>1)throw new Error('Multiple runtime Pages artifacts; refuse ambiguous deployment');
    if(matches.length===1){
      if(String(matches[0].id)!==String(expectedId))
        throw new Error('Runtime Pages artifact differs from uploaded artifact ID');
      consecutive++;
      if(consecutive>=2){
        log('PAGES_RUNTIME_ARTIFACT_VISIBLE '+name+' id='+expectedId+' twice');
        return true;
      }
    }else{
      consecutive=0;
    }
    log('PAGES_RUNTIME_ARTIFACT_PENDING '+i+'/'+attempts+' consecutive='+consecutive);
    if(i<attempts)await sleep(delayMs);
  }
  throw new Error('Uploaded Pages artifact never became stably visible to deploy-pages runtime');
}
module.exports={waitForRuntimeArtifact};
