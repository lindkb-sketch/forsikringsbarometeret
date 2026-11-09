/* Public site links to a PRIVATE Cloudflare Access portal only after provisioning.
   The URL is public configuration, never an authentication secret. */
(() => {
  if (new URLSearchParams(location.search).get('admin')!=='1') return;
  window.addEventListener('DOMContentLoaded', async () => {
    try {
      const result=await fetch('data/broker_admin_config.json?ts='+Date.now(),{cache:'no-store'});
      if (!result.ok) return;
      const config=await result.json();
      if (!config || config.enabled!==true || typeof config.url!=='string') return;
      const url=new URL(config.url);
      if (url.protocol!=='https:'||url.username||url.password||url.hash||url.search||
          url.pathname!=='/'||!/^[a-z0-9.-]+$/i.test(url.hostname)) return;
      const aside=document.querySelector('aside');
      if (!aside||document.getElementById('broker-secure-admin-link')) return;
      const button=document.createElement('a');
      button.id='broker-secure-admin-link';
      button.href=url.href;button.target='_blank';button.rel='noopener noreferrer';
      button.textContent='🔒 Last opp meglerkommentarer (AI)';
      button.setAttribute('aria-label','Åpne privat administrasjon med innlogging');
      button.style.cssText='display:block;margin:10px 12px;width:calc(100% - 24px);padding:12px;background:#136679;color:white;border-radius:8px;text-align:center;text-decoration:none;font-size:12px;font-weight:700';
      aside.append(button);
      const old=document.getElementById('broker-admin-entry');
      if (old) old.hidden=true;
    } catch(e) { console.warn('Privat adminlenke er ikke konfigurert'); }
  });
})();
