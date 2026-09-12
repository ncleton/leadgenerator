"""Shared, recoverable aerial preview without fetching or altering image pixels."""

AERIAL_VIEW_CSS = r"""
.lg-aerial { overflow:hidden; border:1px solid var(--line); border-radius:14px; background:var(--paper); }
.lg-aerial-viewport { position:relative; isolation:isolate; overflow:hidden; aspect-ratio:8/5; }
.lg-aerial-viewport>img { display:block; width:100%; height:100%; object-fit:cover; }
.lg-aerial-reticle { position:absolute; left:50%; top:50%; width:28px; height:28px; transform:translate(-50%,-50%);
  border:2px solid white; border-radius:50%; box-shadow:0 0 0 2px rgba(11,107,88,.9),0 2px 9px rgba(0,0,0,.4); pointer-events:none; }
.lg-aerial-reticle::before,.lg-aerial-reticle::after { content:""; position:absolute; background:white; }
.lg-aerial-reticle::before { left:12px; top:-7px; width:2px; height:38px; }
.lg-aerial-reticle::after { left:-7px; top:12px; width:38px; height:2px; }
.lg-aerial:not([data-image-state="ready"]) .lg-aerial-reticle { display:none; }
.lg-aerial[data-image-state="error"] .lg-aerial-viewport>img { visibility:hidden; }
.lg-aerial[data-image-state="error"] .lg-aerial-viewport::after { content:"Vue IGN indisponible"; position:absolute; inset:0; display:grid; place-items:center; color:var(--muted); font-size:12px; }
.lg-aerial-caption { padding:7px; color:var(--muted); font-size:12px; line-height:1.4; }
.lg-aerial-controls { display:flex; flex-wrap:wrap; align-items:center; gap:5px 10px; margin-top:5px; }
.lg-aerial-controls button,.lg-aerial-controls a { font:inherit; }
.lg-aerial-status { margin:4px 0 0; }
.lg-aerial-small .lg-aerial-viewport { aspect-ratio:4/3; }
:root[data-density="compact"] .lg-aerial-viewport { height:150px; aspect-ratio:auto; }
:root[data-density="compact"] .lg-aerial-small .lg-aerial-viewport { height:104px; }
:root[data-density="compact"] .lg-aerial-caption { padding:5px 7px; font-size:10px; }
@media(max-width:600px) { :root[data-density="compact"] .lg-aerial-small .lg-aerial-viewport { height:82px; } }
"""

AERIAL_VIEW_JS = r"""
(() => {
  const pending = new WeakSet();
  let revision = 0;
  const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[char]);
  const safe = value => { try { const url=new URL(value);return ["https:","http:"].includes(url.protocol)?url.href:null; } catch { return null; } };
  const status = (panel, text) => { const label=panel.querySelector('[data-aerial-status]');if(label){label.textContent=text;label.hidden=!text;} };
  document.addEventListener("load", event => {
    const image=event.target;
    if(image?.matches?.('[data-aerial-image]')) image.closest('[data-aerial]').dataset.imageState="ready";
  }, true);
  document.addEventListener("error", event => {
    const image=event.target;
    if(!image?.matches?.('[data-aerial-image]')) return;
    const panel=image.closest('[data-aerial]');panel.dataset.imageState="error";
    status(panel,"L’image n’a pas été chargée. Réessayez ou ouvrez-la directement.");
  }, true);
  document.addEventListener("click", event => {
    const button=event.target.closest?.('[data-reload-aerial]');
    if(!button) return;
    event.preventDefault();event.stopPropagation();
    const panel=button.closest('[data-aerial]'), previous=panel?.querySelector('[data-aerial-image]');
    if(!previous||pending.has(panel)) return;
    const url=new URL(previous.src);
    // Only the known public IGN GetMap endpoint gets a fresh cache identity.
    // Do not rewrite signed image URLs or change their geographic extent.
    if(url.origin==="https://data.geopf.fr"&&["/wms-r","/wms-r/","/wms-r/wms"].includes(url.pathname)&&url.searchParams.get("REQUEST")==="GetMap")
      url.searchParams.set("_lg_refresh",`${Date.now()}-${++revision}`);
    pending.add(panel);button.disabled=true;status(panel,"Rechargement de l’image IGN…");
    const replacement=new Image();replacement.alt=previous.alt;replacement.referrerPolicy="no-referrer";
    let finished=false;
    const finish = success => {
      if(finished)return;finished=true;clearTimeout(timer);pending.delete(panel);
      replacement.onload=null;replacement.onerror=null;button.disabled=false;
      if(!panel.isConnected)return;
      if(success){replacement.setAttribute('data-aerial-image','');previous.replaceWith(replacement);panel.dataset.imageState="ready";status(panel,"");}
      else {if(!previous.naturalWidth)panel.dataset.imageState="error";status(panel,"Le rechargement a échoué. Réessayez ou ouvrez l’image directement.");}
    };
    const timer=setTimeout(()=>finish(false),12000);
    replacement.onload=async()=>{try{await replacement.decode();finish(true);}catch{finish(false);}};
    replacement.onerror=()=>finish(false);
    replacement.src=url.href;
  });
  window.leadGeneratorAerial = {
    render({image,alt,caption,source,small=false}) {
      image=safe(image);source=safe(source);if(!image)return "";
      return `<div class="lg-aerial${small?' lg-aerial-small':''}" data-aerial data-image-state="loading"><div class="lg-aerial-viewport"><img data-aerial-image src="${esc(image)}" alt="${esc(alt)}" referrerpolicy="no-referrer"><span class="lg-aerial-reticle" aria-hidden="true"></span></div><div class="lg-aerial-caption">${esc(caption)}${source?` <a href="${esc(source)}" target="_blank" rel="noopener noreferrer">Source IGN ↗</a>`:""}<div class="lg-aerial-controls"><button type="button" class="button" data-reload-aerial>Recharger l’image</button><a href="${esc(image)}" target="_blank" rel="noopener noreferrer">Ouvrir l’image IGN ↗</a></div><p class="lg-aerial-status" data-aerial-status role="status" aria-live="polite" hidden></p></div></div>`;
    }
  };
})();
"""
