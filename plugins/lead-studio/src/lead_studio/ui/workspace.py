"""MCP Apps workspace for the complete human-reviewed lead workflow."""

from __future__ import annotations

from lead_studio.ui.bridge import MCP_APP_BRIDGE_JS

LEAD_WORKSPACE_UI_URI = "ui://lead-studio/lead-workspace/v7.html"
LEAD_WORKSPACE_LEGACY_UI_URIS = tuple(
    f"ui://lead-studio/lead-workspace/v{version}.html" for version in range(1, 7)
)

LEAD_WORKSPACE_RESOURCE_META = {
    "ui": {
        "prefersBorder": False,
        "csp": {
            "connectDomains": [],
            "resourceDomains": [
                "https://*",
                "https://app.fullenrich.com",
                "https://media.licdn.com",
                "https://data.geopf.fr",
            ],
        },
    },
    "openai/widgetDescription": (
        "Pilote les agents d'objectif, le sourcing, la qualification, les "
        "contacts, les visuels, l'enrichissement et la préparation HubSpot."
    ),
    "openai/widgetPrefersBorder": False,
    "openai/widgetCSP": {
        "connect_domains": [],
        "resource_domains": [
            "https://*",
            "https://app.fullenrich.com",
            "https://media.licdn.com",
            "https://data.geopf.fr",
        ],
    },
}

LEAD_WORKSPACE_TOOL_META = {
    "ui": {"resourceUri": LEAD_WORKSPACE_UI_URI},
    "openai/toolInvocation/invoking": "Mise en forme de la sélection…",
    "openai/toolInvocation/invoked": "Espace Lead Generator prêt",
}


LEAD_WORKSPACE_HTML = r"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <title>Lead Generator — Workspace</title>
  <style>
    :root {
      --ink:#17211f; --muted:#68736f; --paper:#f5f6f3; --surface:#ffffff;
      --surface-2:#eef2ef; --line:#dce2de; --brand:#087461; --brand-soft:#e1f2ed;
      --amber:#a45b14; --amber-soft:#fff1df; --violet:#71538c; --violet-soft:#f0e8f5;
      --danger:#a63b34; --danger-soft:#fae7e4; --shadow:0 12px 40px rgba(24,42,37,.08);
      color-scheme:light; font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif;
    }
    :root[data-theme="dark"] {
      --ink:#edf6f2; --muted:#a8b9b3; --paper:#0e1715; --surface:#17221f;
      --surface-2:#22312d; --line:#30413c; --brand:#76d7bc; --brand-soft:#1e443b;
      --amber:#efb66f; --amber-soft:#49331d; --violet:#c8a7e3; --violet-soft:#3a2d46;
      --danger:#f29990; --danger-soft:#492725; --shadow:none; color-scheme:dark;
    }
    * { box-sizing:border-box; }
    html,body { margin:0; min-width:0; background:transparent; color:var(--ink); }
    button,input,a { font:inherit; }
    button { color:inherit; }
    #app { min-height:560px; overflow:hidden; border:1px solid var(--line); border-radius:22px;
      background:var(--paper); box-shadow:var(--shadow); }
    .header { padding:22px 24px 18px; background:var(--surface); border-bottom:1px solid var(--line); }
    .head-row { display:flex; align-items:center; justify-content:space-between; gap:24px; }
    .header-copy { min-width:0; max-width:720px; }
    .eyebrow { margin:0 0 7px; color:var(--brand); font-size:.68rem; font-weight:850;
      letter-spacing:.13em; text-transform:uppercase; }
    h1,h2,h3,p { margin-top:0; }
    h1 { margin-bottom:7px; font-size:clamp(1.38rem,2.4vw,1.8rem); line-height:1.12; letter-spacing:-.025em; }
    .sub { margin:0; color:var(--muted); font-size:.84rem; line-height:1.45; }
    .metrics { display:grid; grid-template-columns:repeat(3,minmax(82px,1fr)); gap:8px; flex:0 0 auto; }
    .metric { min-width:88px; padding:9px 11px; border:1px solid var(--line); border-radius:13px;
      background:var(--paper); }
    .metric strong,.metric span { display:block; }
    .metric strong { font-size:1rem; line-height:1.1; }
    .metric span { margin-top:3px; color:var(--muted); font-size:.62rem; text-transform:uppercase; letter-spacing:.055em; }
    .filters { display:flex; gap:6px; flex-wrap:wrap; margin-top:9px; }
    .chip { display:inline-flex; align-items:center; min-height:28px; padding:4px 9px; border-radius:999px;
      border:1px solid var(--line); background:var(--paper); font-size:.72rem; }
    .chip.brand { color:var(--brand); border-color:color-mix(in srgb,var(--brand) 32%,var(--line)); background:var(--brand-soft); }
    .chip.warn { color:var(--amber); background:var(--amber-soft); }
    .brief { margin-top:13px; color:var(--muted); font-size:.75rem; }
    .brief>summary,.source-notes summary { width:max-content; max-width:100%; padding:6px 10px;
      border:1px solid var(--line); border-radius:999px; background:var(--paper); cursor:pointer; font-weight:720; }
    .brief-body { margin-top:9px; padding:11px 12px; border:1px solid var(--line); border-radius:12px; background:var(--paper); }
    .brief-body p { margin:0; line-height:1.45; }
    .source-notes { margin-top:8px; color:var(--muted); font-size:.75rem; }
    .source-notes summary { width:max-content; max-width:100%; padding:5px 9px; border:1px solid var(--line);
      border-radius:999px; background:var(--paper); cursor:pointer; font-weight:720; }
    .source-notes ul { margin:8px 0 0; padding:10px 12px 10px 28px; border:1px solid var(--line);
      border-radius:11px; background:var(--paper); }
    .source-notes li + li { margin-top:5px; }
    .tabs { display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:4px; padding:8px 12px; background:var(--surface);
      border-bottom:1px solid var(--line); }
    .tab { min-width:0; min-height:40px; padding:8px 7px; border:0; border-radius:10px; background:transparent;
      cursor:pointer; font-size:.78rem; font-weight:760; white-space:nowrap; }
    .tab[aria-selected="true"] { color:var(--brand); background:var(--brand-soft); }
    .badge { display:inline-grid; place-items:center; min-width:20px; height:20px; margin-left:5px;
      border-radius:999px; background:var(--surface); font-size:.66rem; }
    .main { padding:18px; min-height:410px; }
    .view { display:none; }
    .view.active { display:block; }
    .section-head { display:flex; align-items:center; justify-content:space-between; gap:12px;
      margin-bottom:13px; }
    .section-head h2 { margin:0; font-size:1.02rem; }
    .hint { color:var(--muted); font-size:.77rem; }
    .pipeline { display:grid; grid-template-columns:repeat(4,minmax(190px,1fr)); gap:10px; overflow:auto; }
    .objective-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:10px; }
    .objective-card { padding:14px; border:1px solid var(--line); border-radius:16px; background:var(--surface); }
    .objective-card.active { border-color:var(--brand); box-shadow:0 0 0 2px var(--brand-soft); }
    .objective-head { display:flex; align-items:flex-start; justify-content:space-between; gap:10px; }
    .agent-identity { display:flex; align-items:center; gap:9px; }
    .agent-emoji { display:grid; place-items:center; width:38px; height:38px; border-radius:12px;
      background:var(--brand-soft); font-size:1.25rem; }
    .objective-section { margin-top:10px; padding-top:9px; border-top:1px solid var(--line); }
    .objective-section strong { display:block; margin-bottom:4px; font-size:.72rem; text-transform:uppercase;
      letter-spacing:.06em; }
    .objective-list { margin:5px 0 0; padding-left:18px; color:var(--muted); font-size:.74rem; }
    .objective-list li+li { margin-top:4px; }
    .stage { min-height:365px; padding:11px; border:1px solid var(--line); border-radius:15px; background:var(--surface-2); }
    .stage-title { display:flex; align-items:center; justify-content:space-between; margin-bottom:10px;
      font-size:.74rem; font-weight:850; text-transform:uppercase; letter-spacing:.07em; }
    .stage-list { display:grid; gap:8px; }
    .mini-card { padding:10px; border:1px solid var(--line); border-radius:12px; background:var(--surface); cursor:pointer; }
    .mini-card:hover { border-color:var(--brand); }
    .mini-card h3 { margin:0 0 4px; font-size:.86rem; }
    .mini-card p { margin:0; color:var(--muted); font-size:.72rem; }
    .company-grid { display:grid; grid-template-columns:minmax(0,1fr); gap:14px; }
    .contact-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:10px; align-items:start; }
    .card { position:relative; overflow:hidden; border:1px solid var(--line); border-radius:16px; background:var(--surface); }
    .company-card { display:grid; grid-template-columns:minmax(220px,29%) minmax(0,1fr); align-items:start; }
    .company-media { min-width:0; border-right:1px solid var(--line); background:var(--surface-2); }
    .cover { position:relative; height:174px; display:grid; place-items:center; overflow:hidden;
      border-bottom:1px solid var(--line); background:linear-gradient(145deg,var(--brand-soft),var(--surface-2)); }
    .cover>img:not(.company-logo) { position:absolute; inset:0; width:100%; height:100%; object-fit:cover; }
    .cover .initial { font-size:2rem; color:var(--brand); font-weight:900; letter-spacing:-.04em; }
    .company-logo { position:absolute; z-index:2; top:12px; left:12px; width:70px; height:48px; padding:7px;
      border:1px solid rgba(20,40,35,.08); border-radius:11px; background:rgba(255,255,255,.96); object-fit:contain!important; }
    .intel-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:9px; margin-top:10px; }
    .intel-block { min-width:0; padding:10px 11px; border:1px solid var(--line); border-radius:11px; background:var(--paper); }
    .intel-block h4 { margin:0 0 6px; font-size:.74rem; text-transform:uppercase; letter-spacing:.05em; }
    .intel-block p { margin:0; font-size:.76rem; }
    .aerial-small { position:relative; overflow:hidden; background:var(--surface-2); }
    .aerial-small img { display:block; width:100%; aspect-ratio:4/3; object-fit:cover; }
    .aerial-small::after { content:""; position:absolute; left:50%; top:50%; width:18px; height:18px;
      transform:translate(-50%,-50%); border:2px solid white; border-radius:50%; box-shadow:0 0 0 2px var(--brand); }
    .aerial-caption { padding:8px 10px; border-top:1px solid var(--line); color:var(--muted); font-size:.68rem; line-height:1.35; }
    .card-body { padding:16px 17px 17px; }
    .card h3 { margin:0 0 4px; font-size:.98rem; }
    .company-card h3 { padding-right:42px; font-size:1.12rem; letter-spacing:-.012em; }
    .company-description { margin:12px 0; color:var(--ink); font-size:.82rem; line-height:1.55; }
    .company-facts { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:0 18px; }
    .meta { color:var(--muted); font-size:.74rem; }
    .check-wrap { position:absolute; z-index:2; top:10px; right:10px; display:grid; place-items:center;
      width:31px; height:31px; border:1px solid var(--line); border-radius:9px; background:var(--surface); }
    .check { width:17px; height:17px; accent-color:var(--brand); }
    .fact-line { display:flex; justify-content:space-between; gap:10px; padding:7px 0;
      border-bottom:1px solid var(--line); font-size:.75rem; }
    .fact-line:last-child { border-bottom:0; }
    .fact-line span:first-child { color:var(--muted); }
    .evidence { margin-top:9px; padding:9px; border:1px solid var(--line); border-radius:11px; background:var(--paper); }
    .evidence summary { cursor:pointer; font-size:.74rem; font-weight:780; }
    .evidence-list { display:grid; gap:7px; margin-top:8px; }
    .evidence-row { padding:8px; border-left:3px solid var(--line); background:var(--surface); font-size:.72rem; }
    .evidence-row.signal { border-left-color:var(--brand); }
    .evidence-row.hypothesis { border-left-color:var(--violet); }
    .evidence-row.missing { border-left-color:var(--amber); }
    .evidence-row a { color:var(--brand); }
    .actions { display:flex; flex-wrap:wrap; gap:7px; margin-top:11px; }
    .button { display:inline-flex; align-items:center; justify-content:center; min-height:37px; padding:7px 11px;
      border:1px solid var(--line); border-radius:10px; background:var(--surface); color:var(--ink);
      text-decoration:none; cursor:pointer; font-weight:740; font-size:.76rem; }
    .button.primary { border-color:var(--brand); background:var(--brand); color:white; }
    :root[data-theme="dark"] .button.primary { color:#10201c; }
    .button:disabled { opacity:.45; cursor:not-allowed; }
    .avatar { width:62px; height:62px; display:grid; place-items:center; margin-bottom:10px;
      overflow:hidden; border:2px solid var(--surface); border-radius:18px; background:var(--brand-soft);
      color:var(--brand); font-weight:900; font-size:1.2rem; }
    .avatar img { width:100%; height:100%; object-fit:cover; }
    .contact-top { display:flex; align-items:flex-start; gap:11px; }
    .contact-data { margin-top:10px; padding:9px; border-radius:11px; background:var(--paper); }
    .contact-value { display:flex; align-items:center; gap:7px; min-height:27px; font-size:.76rem; }
    .status-dot { width:8px; height:8px; border-radius:50%; background:var(--muted); }
    .status-dot.ok { background:var(--brand); }
    .status-dot.pending { background:var(--amber); }
    .gallery { display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,1fr)); gap:11px; }
    .visual { overflow:hidden; border:1px solid var(--line); border-radius:15px; background:var(--surface); }
    .visual-frame { height:150px; display:grid; place-items:center; overflow:hidden; background:var(--surface-2); }
    .visual-frame img { width:100%; height:100%; object-fit:contain; }
    .visual-fallback { padding:18px; color:var(--muted); text-align:center; font-size:.76rem; }
    .visual-info { padding:11px; }
    .integrations { display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:10px; margin-bottom:14px; }
    .integration { padding:12px; border:1px solid var(--line); border-radius:14px; background:var(--surface); }
    .integration-head { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:7px; }
    .integration h3 { margin:0; font-size:.88rem; text-transform:capitalize; }
    .status { padding:4px 7px; border-radius:999px; background:var(--surface-2); font-size:.66rem; font-weight:780; }
    .status.connected { color:var(--brand); background:var(--brand-soft); }
    .status.invalid { color:var(--danger); background:var(--danger-soft); }
    .status.configured { color:var(--amber); background:var(--amber-soft); }
    .crm-layout { display:grid; grid-template-columns:minmax(0,1.2fr) minmax(250px,.8fr); gap:12px; }
    .panel { padding:14px; border:1px solid var(--line); border-radius:15px; background:var(--surface); }
    .panel h3 { margin-bottom:11px; font-size:.92rem; }
    label { display:block; margin:10px 0 5px; color:var(--muted); font-size:.72rem; font-weight:700; }
    input[type="text"],input[type="search"] { width:100%; min-height:40px; padding:8px 10px; color:var(--ink);
      border:1px solid var(--line); border-radius:10px; background:var(--paper); }
    .preview-list { display:grid; gap:7px; max-height:260px; overflow:auto; }
    .preview-row { display:flex; align-items:center; justify-content:space-between; gap:8px; padding:8px;
      border:1px solid var(--line); border-radius:10px; font-size:.75rem; }
    .empty { padding:38px 18px; border:1px dashed var(--line); border-radius:14px; color:var(--muted); text-align:center; }
    .footer { display:flex; align-items:center; justify-content:space-between; gap:10px;
      padding:12px 16px; border-top:1px solid var(--line); background:var(--surface); }
    .footer-actions { display:flex; flex-wrap:wrap; justify-content:flex-end; gap:7px; }
    .loading { min-height:560px; display:flex; align-items:center; justify-content:center;
      gap:11px; padding:30px; color:var(--muted); text-align:center; font-weight:700; }
    .spinner { display:inline-block; width:22px; height:22px; flex:0 0 auto;
      border:3px solid var(--line); border-top-color:var(--brand); border-radius:50%;
      animation:spin .75s linear infinite; }
    @keyframes spin { to { transform:rotate(360deg); } }
    .error { padding:36px; color:var(--muted); }
    .error { color:var(--danger); }
    @media(max-width:760px) {
      #app { border-radius:16px; min-height:620px; }
      .head-row,.footer { align-items:flex-start; flex-direction:column; }
      .metrics { width:100%; margin-top:6px; }
      .tabs { grid-template-columns:repeat(3,minmax(0,1fr)); }
      .main { padding:11px; }
      .pipeline { grid-template-columns:repeat(4,250px); }
      .company-card { grid-template-columns:1fr; }
      .company-media { border-right:0; border-bottom:1px solid var(--line); }
      .cover { height:150px; }
      .aerial-small img { aspect-ratio:8/5; }
      .intel-grid,.company-facts { grid-template-columns:1fr; }
      .crm-layout { grid-template-columns:1fr; }
      .footer-actions { justify-content:flex-start; }
    }
    @media(prefers-reduced-motion:reduce) { * { transition:none!important; } .spinner { animation:none; } }
  </style>
</head>
<body>
  <main id="app"><div class="loading" role="status" aria-live="polite"><span class="spinner" aria-hidden="true"></span><span id="loading-message">Ouverture de Lead Generator…</span></div></main>
  <script>
    (() => {
      "use strict";
      const app = document.getElementById("app");
      let data = null, dataFingerprint = null, activeView = "pipeline", searchText = "", selected = new Set();
      const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({
        "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
      })[char]);
      const safeUrl = value => { try { const u=new URL(String(value||"")); return ["http:","https:"].includes(u.protocol)?u.href:null; } catch { return null; } };
      const initials = value => String(value||"?").split(/\s+/).slice(0,2).map(x=>x[0]||"").join("").toUpperCase();
      const leads = () => (data?.leads||[]).filter(lead => !searchText || `${lead.company_name} ${lead.naf_code||""} ${lead.activity||""}`.toLowerCase().includes(searchText.toLowerCase()));
      const objectives = () => data?.objectives||[];
      const activeObjective = () => objectives().find(item => (item.objective_id||item.id)===data?.active_objective_id)||null;
      const selectedLeads = () => (data?.leads||[]).filter(lead => selected.has(lead.id));
      const contacts = () => (data?.leads||[]).flatMap(lead => (lead.contacts||[]).map(contact => ({...contact,lead})));
      const visuals = () => (data?.leads||[]).flatMap(lead => {
        const rows=[...(lead.visuals||[])];
        if(lead.logo_url&&!rows.some(x=>x.image_url===lead.logo_url)) rows.push({kind:"logo",image_url:lead.logo_url,source_url:lead.website_url,evidence:"Logo retenu pour la fiche",confidence:"review"});
        if(lead.representative_image_url&&!rows.some(x=>x.image_url===lead.representative_image_url)) rows.push({kind:"representative_image",image_url:lead.representative_image_url,source_url:lead.website_url,evidence:"Visuel retenu pour la fiche",confidence:"review"});
        const aerial=parkingAerialUrl(lead);
        if(aerial&&!rows.some(x=>x.kind==="aerial_image")) rows.push({kind:"aerial_image",image_url:aerial,source_url:lead.aerial_source_url,evidence:"Orthophoto IGN resserrée sur le bâtiment et son parking",confidence:"high"});
        return rows.map(visual=>({...visual,lead}));
      });
      const factValue = (lead, pattern) => (lead?.observed_facts||[]).find(fact => pattern.test(fact.label||""))?.value || null;
      const employeeBand = lead => lead?.employee_band_label || factValue(lead,/effectif/i);
      const evidenceDate = item => item.event_date||item.published_at||item.observed_at||null;
      const sourceLink = item => { const url=safeUrl(item?.source_url);return url?`<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">preuve ↗</a>`:""; };
      const filterLabels = {activity_section:"Secteur",region:"Région",department:"Département",naf_codes:"Codes NAF",category:"Catégorie",min_employees:"Effectif min.",max_employees:"Effectif max."};
      const filterValue = (key,value) => key==="activity_section"&&value==="F"?"Construction":key==="region"&&String(value)==="32"?"Hauts-de-France":Array.isArray(value)?value.join(", "):value;
      const visibleFilters = filters => filters.filter(([key])=>Object.hasOwn(filterLabels,key));
      const parkingAerialUrl = lead => {
        const focus=lead?.aerial_focus||lead?.location,lat=Number(focus?.latitude),lon=Number(focus?.longitude);
        if(!Number.isFinite(lat)||!Number.isFinite(lon)) return safeUrl(lead?.aerial_image_url);
        const halfLat=.00045,halfLon=halfLat*(800/500)/Math.cos(lat*Math.PI/180);
        const bbox=[lon-halfLon,lat-halfLat,lon+halfLon,lat+halfLat].map(value=>value.toFixed(7)).join(",");
        const params=new URLSearchParams({SERVICE:"WMS",VERSION:"1.3.0",REQUEST:"GetMap",LAYERS:"HR.ORTHOIMAGERY.ORTHOPHOTOS",STYLES:"",CRS:"CRS:84",BBOX:bbox,WIDTH:"800",HEIGHT:"500",FORMAT:"image/jpeg"});
        return `https://data.geopf.fr/wms-r/wms?${params}`;
      };
      function extractPayload(value) {
        if(!value) return null;
        if(value.kind==="lead_workspace") return value;
        if(value.structuredContent?.kind==="lead_workspace") return value.structuredContent;
        if(value.structured_content?.kind==="lead_workspace") return value.structured_content;
        if(value.output?.kind==="lead_workspace") return value.output;
        return null;
      }
      function applyGlobals(globals) {
        const theme=globals?.theme||window.openai?.theme;
        if(theme) document.documentElement.dataset.theme=theme==="dark"?"dark":"light";
      }
      function hydrate(incoming) {
        const payload=extractPayload(incoming); if(!payload||!Array.isArray(payload.leads)) return;
        const fingerprint=JSON.stringify(payload); if(fingerprint===dataFingerprint) return;
        dataFingerprint=fingerprint;
        data=payload; const saved=window.openai?.widgetState||{};
        const ids=new Set(data.leads.map(lead=>lead.id));
        selected=new Set((saved.selectedLeadIds||data.selected_ids||[]).filter(id=>ids.has(id)));
        activeView=["objectives","pipeline","companies","contacts","visuals","hubspot"].includes(saved.activeView||data.initial_view)?(saved.activeView||data.initial_view):"pipeline";
        searchText=String(saved.searchText||""); render();
      }
      function persist() {
        window.openai?.setWidgetState?.({activeView,selectedLeadIds:[...selected],searchText});
      }
      function render() {
        const all=data.leads||[], foundContacts=contacts().filter(x=>x.work_email||x.phone).length;
        const objective=activeObjective();
        const filters=visibleFilters(Object.entries(data.search?.filters||{}).filter(([,v])=>v!==null&&v!==""&&(!Array.isArray(v)||v.length)));
        const title=all.length?`${all.length} entreprise${all.length===1?"":"s"} qualifiée${all.length===1?"":"s"}`:"Pipeline de prospection";
        app.innerHTML=`<header class="header"><div class="head-row"><div class="header-copy"><p class="eyebrow">Lead Generator</p>
          <h1>${esc(title)}</h1><p class="sub">${objective?`${esc(objective.agent?.emoji||"🎯")} ${esc(objective.agent?.name||objective.name||objective.objective_name||objective.objective_id)}`:"Assistant général"} · recherche publique sourcée, sous validation humaine.</p></div>
          <div class="metrics"><div class="metric"><strong>${all.length}</strong><span>entreprises</span></div><div class="metric"><strong>${contacts().length}</strong><span>contacts</span></div><div class="metric"><strong>${foundContacts}</strong><span>coordonnées</span></div></div></div>
          <details class="brief"><summary>Voir le périmètre et les limites</summary><div class="brief-body">${data.search?.summary?`<p>${esc(data.search.summary)}</p>`:""}<div class="filters">${filters.map(([k,v])=>`<span class="chip brand">${esc(filterLabels[k])} · ${esc(filterValue(k,v))}</span>`).join("")}</div>${sourceNotes()}</div></details></header>
          <nav class="tabs" role="tablist" aria-label="Parcours Lead Generator">${tab("objectives","Objectifs",objectives().length)}${tab("pipeline","Pipeline",all.length)}${tab("companies","Entreprises",all.length)}${tab("contacts","Contacts",contacts().length)}${tab("visuals","Visuels",visuals().length)}${tab("hubspot","HubSpot",selected.size)}</nav>
          <section class="main"><section id="view" class="view active"></section></section>
          <footer class="footer"><span><strong>${selected.size}</strong> lead${selected.size===1?"":"s"} retenu${selected.size===1?"":"s"}</span><div class="footer-actions"><button class="button" data-global="compare" ${selected.size<2?"disabled":""}>Comparer</button><button class="button primary" data-global="qualify" ${selected.size<1?"disabled":""}>Enrichir la sélection</button></div></footer>`;
        app.querySelectorAll("[data-view]").forEach(b=>b.addEventListener("click",()=>{activeView=b.dataset.view;persist();render();}));
        app.querySelector("[data-global='compare']")?.addEventListener("click",compare);
        app.querySelector("[data-global='qualify']")?.addEventListener("click",qualify);
        renderView();
      }
      function tab(id,label,count) { return `<button class="tab" role="tab" data-view="${id}" aria-selected="${activeView===id}">${label}<span class="badge">${count}</span></button>`; }
      function renderView() {
        const target=document.getElementById("view"); if(!target)return;
        if(activeView==="objectives") renderObjectives(target);
        if(activeView==="pipeline") renderPipeline(target);
        if(activeView==="companies") renderCompanies(target);
        if(activeView==="contacts") renderContacts(target);
        if(activeView==="visuals") renderVisuals(target);
        if(activeView==="hubspot") renderHubspot(target);
      }
      function renderObjectives(target) {
        const rows=objectives();
        target.innerHTML=`<div class="section-head"><div><h2>Agents d'objectif</h2><span class="hint">Chaque agent conserve ses consignes, exemples, contexte, documents et conversations.</span></div><button class="button primary" data-create-objective>Créer un objectif</button></div><div class="objective-grid">${rows.length?rows.map(objectiveCard).join(""):`<div class="empty">Aucun objectif. Créez-en un pour cadrer les recherches et les contacts.</div>`}</div>`;
        target.querySelector("[data-create-objective]")?.addEventListener("click",()=>followUp("Crée un nouvel agent d'objectif Lead Generator. Demande seulement les informations réellement manquantes, puis enregistre l'objectif, ses consignes, exemples, rôles cibles et critères de preuve dans le stockage privé local.",false));
        target.querySelectorAll("[data-activate-objective]").forEach(button=>button.addEventListener("click",()=>activateObjective(button.dataset.activateObjective)));
        target.querySelectorAll("[data-edit-objective]").forEach(button=>button.addEventListener("click",()=>editObjective(button.dataset.editObjective)));
        target.querySelectorAll("[data-attach-objective]").forEach(button=>button.addEventListener("click",()=>attachObjectiveDocument(button.dataset.attachObjective)));
      }
      function objectiveCard(objective) {
        const id=objective.objective_id||objective.id, agent=objective.agent||{}, active=id===data.active_objective_id;
        const instructions=agent.instructions||objective.instructions||[], examples=agent.examples||objective.examples||[], documents=agent.documents||objective.documents||[];
        const instructionRows=Array.isArray(instructions)?instructions:[instructions];
        return `<article class="objective-card ${active?"active":""}"><div class="objective-head"><div class="agent-identity"><span class="agent-emoji">${esc(agent.emoji||"🎯")}</span><div><h3>${esc(agent.name||objective.name||objective.objective_name||id)}</h3><p class="meta">${esc(objective.goal_natural||objective.description||objective.offer_name||"Objectif à compléter")}</p></div></div><span class="chip ${active?"brand":""}">${active?"Actif":esc(objective.status||"active")}</span></div>
          <div class="objective-section"><strong>Consignes</strong>${instructionRows.length?`<ul class="objective-list">${instructionRows.slice(0,4).map(item=>`<li>${esc(item)}</li>`).join("")}</ul>`:`<p class="meta">À compléter</p>`}</div>
          <div class="objective-section"><div class="fact-line"><span>Exemples</span><strong>${examples.length||0}</strong></div><div class="fact-line"><span>Documents</span><strong>${documents.length||0}</strong></div><div class="fact-line"><span>Rôles cibles</span><strong>${(agent.target_roles||objective.target_roles||[]).length||0}</strong></div></div>
          <div class="actions"><button class="button ${active?"":"primary"}" data-activate-objective="${esc(id)}">${active?"Parler à l'agent":"Activer"}</button><button class="button" data-edit-objective="${esc(id)}">Modifier</button><button class="button" data-attach-objective="${esc(id)}">Associer un document</button></div></article>`;
      }
      const stageOf=lead=>lead.pipeline?.crm_sync==="complete"?"crm":lead.pipeline?.contact_enrichment==="complete"||lead.pipeline?.contact_enrichment==="review"?"enrichment":lead.pipeline?.contact_discovery==="complete"||lead.pipeline?.contact_discovery==="review"?"contact":"company";
      function renderPipeline(target) {
        const stages=[
          ["company","01 · Entreprises","Qualifier le site et les signaux"],
          ["contact","02 · Décideurs","Valider nom, poste et société"],
          ["enrichment","03 · Enrichissement","Enrow puis FullEnrich sous accord"],
          ["crm","04 · HubSpot","Liste et propriétaire confirmés"]
        ];
        target.innerHTML=`<div class="pipeline">${stages.map(([id,title,desc])=>{const rows=(data.leads||[]).filter(x=>stageOf(x)===id);return `<section class="stage"><div class="stage-title"><span>${title}</span><span class="badge">${rows.length}</span></div><p class="hint">${desc}</p><div class="stage-list">${rows.length?rows.map(miniCard).join(""):`<div class="empty">Aucun lead à cette étape.</div>`}</div></section>`;}).join("")}</div>`;
        bindLeadButtons(target);
      }
      function miniCard(lead) { const contact=(lead.contacts||[])[0],workforce=employeeBand(lead);return `<article class="mini-card" data-lead-action="${esc(lead.id)}"><h3>${esc(lead.company_name)}</h3><p>${esc(contact?`${contact.name} · ${contact.role||"poste à confirmer"}`:(lead.naf_code||lead.activity||"Activité à confirmer"))}</p><div class="filters"><span class="chip">${esc(lead.confidence_score==null?"score —":`${lead.confidence_score}% confiance`)}</span>${workforce?`<span class="chip">${esc(workforce)}</span>`:""}</div></article>`; }
      function renderCompanies(target) {
        target.innerHTML=`<div class="section-head"><div><h2>Entreprises</h2><span class="hint">Faits juridiques, signaux et informations manquantes.</span></div><input aria-label="Filtrer les entreprises" type="search" value="${esc(searchText)}" placeholder="Filtrer par nom, NAF, activité…"></div><div class="company-grid">${leads().length?leads().map(companyCard).join(""):`<div class="empty">Aucune entreprise ne correspond au filtre.</div>`}</div>`;
        const input=target.querySelector("input[type='search']"); input?.addEventListener("input",()=>{searchText=input.value;persist();renderView();}); bindLeadButtons(target); bindChecks(target);
      }
      function companyCard(lead) {
        const image=safeUrl(lead.representative_image_url), logo=safeUrl(lead.logo_url), aerial=parkingAerialUrl(lead), website=safeUrl(lead.website_url), legal=safeUrl(lead.legal_profile_url), workforce=employeeBand(lead),focus=lead.aerial_focus||lead.location;
        return `<article class="card company-card"><label class="check-wrap"><input class="check" data-select="${esc(lead.id)}" type="checkbox" ${selected.has(lead.id)?"checked":""} aria-label="Sélectionner ${esc(lead.company_name)}"></label><div class="company-media"><div class="cover"><span class="initial">${esc(initials(lead.company_name))}</span>${image?`<img src="${esc(image)}" alt="Image représentative de ${esc(lead.company_name)}" onerror="this.remove()">`:""}${logo?`<img class="company-logo" src="${esc(logo)}" alt="Logo de ${esc(lead.company_name)}" onerror="this.remove()">`:""}</div>${aerial?`<div class="aerial-small"><img src="${esc(aerial)}" alt="Vue aérienne centrée sur ${esc(focus?.label||lead.company_name)}" onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'visual-fallback',textContent:'Vue IGN indisponible — ouvrir la source.'}))"><div class="aerial-caption">Vue IGN resserrée sur ${esc(focus?.label||"l’établissement")} · échelle bâtiment / parking</div></div>`:""}</div><div class="card-body"><h3>${esc(lead.company_name)}</h3><p class="meta">${lead.siren?`SIREN ${esc(lead.siren)} · `:""}${esc(lead.naf_code||"NAF à confirmer")}</p>${lead.company_description?`<p class="company-description">${esc(lead.company_description)}</p>`:""}
          <div class="company-facts"><div class="fact-line"><span>Activité</span><strong>${esc(lead.naf_label||lead.activity||"À qualifier")}</strong></div><div class="fact-line"><span>Effectif</span><strong>${esc(workforce||"À rechercher")}</strong></div><div class="fact-line"><span>Signaux sourcés</span><strong>${(lead.opportunity_signals||[]).length}</strong></div><div class="fact-line"><span>Informations manquantes</span><strong>${(lead.missing_information||[]).length}</strong></div></div>${researchEvidence(lead)}
          ${(lead.news_summary||lead.outreach_angle)?`<div class="intel-grid">${lead.news_summary?`<div class="intel-block"><h4>Actualité condensée</h4><p>${esc(lead.news_summary)}</p></div>`:""}${lead.outreach_angle?`<div class="intel-block"><h4>Premier angle</h4><p>${esc(lead.outreach_angle)}</p></div>`:""}</div>`:""}
          <div class="actions">${website?`<a class="button" href="${esc(website)}" target="_blank" rel="noopener noreferrer">Site officiel ↗</a>`:""}${legal?`<a class="button" href="${esc(legal)}" target="_blank" rel="noopener noreferrer">Fiche légale ↗</a>`:""}<button class="button primary" data-lead-action="${esc(lead.id)}">Actualiser la fiche</button></div></div></article>`;
      }
      function researchEvidence(lead) {
        const facts=lead.observed_facts||[], signals=lead.opportunity_signals||[], hypotheses=lead.hypotheses_to_validate||[], missing=lead.missing_information||[];
        const total=facts.length+signals.length+hypotheses.length+missing.length;if(!total)return "";
        const factRows=facts.filter(item=>!/effectif/i.test(item.label||"")).map(item=>`<div class="evidence-row"><strong>${esc(item.label)}</strong> · ${esc(item.value)} ${evidenceDate(item)?`<span class="meta">· ${esc(evidenceDate(item))}</span>`:""} ${sourceLink(item)}</div>`);
        const signalRows=signals.map(item=>`<div class="evidence-row signal"><strong>Signal</strong> · ${esc(item.signal)}<br>${esc(item.evidence)} ${evidenceDate(item)?`<span class="meta">· ${esc(evidenceDate(item))}</span>`:""} ${sourceLink(item)}</div>`);
        const hypothesisRows=hypotheses.map(item=>`<div class="evidence-row hypothesis"><strong>Hypothèse à valider</strong> · ${esc(item.hypothesis)}<br>${esc(item.rationale)}</div>`);
        const missingRows=missing.map(item=>`<div class="evidence-row missing"><strong>Manquant</strong> · ${esc(item)}</div>`);
        return `<details class="evidence"><summary>Voir les faits, preuves et hypothèses (${total})</summary><div class="evidence-list">${[...factRows,...signalRows,...hypothesisRows,...missingRows].join("")}</div></details>`;
      }
      function renderContacts(target) {
        const rows=contacts().sort((a,b)=>(a.rank||99)-(b.rank||99)); target.innerHTML=`<div class="section-head"><div><h2>Décideurs et contacts</h2><span class="hint">Profils publics d'abord. Email et numéro restent séparés et soumis à confirmation.</span></div></div><div class="contact-grid">${rows.length?rows.map(contactCard).join(""):`<div class="empty">Aucun décideur validé. Lancez l'enrichissement public sur la sélection.</div>`}</div>`;
        target.querySelectorAll("[data-public-enrich]").forEach(b=>b.addEventListener("click",()=>enrichPublicContact(b.dataset.publicEnrich,b.dataset.contact)));
        target.querySelectorAll("[data-add-contact]").forEach(b=>b.addEventListener("click",()=>addContact(b.dataset.addContact,b.dataset.contact)));
        target.querySelectorAll("[data-coordinate]").forEach(b=>b.addEventListener("click",()=>prepareEnrichment(b.dataset.coordinate,b.dataset.contact,b.dataset.field)));
        target.querySelectorAll("[data-find-contact]").forEach(b=>b.addEventListener("click",()=>findContact(b.dataset.findContact)));
        if(!rows.length&&selected.size) target.innerHTML+=`<div class="actions"><button class="button primary" data-find-contact="selection">Trouver les décideurs de la sélection</button></div>`,target.querySelector("[data-find-contact]")?.addEventListener("click",()=>findContact("selection"));
      }
      function contactCard({lead,...contact}) {
        const photo=safeUrl(contact.profile_image_url), linkedin=safeUrl(contact.linkedin_url), source=safeUrl(contact.source_url), publicDone=contact.public_profile_status==="complete", added=Boolean(contact.added_to_contacts||contact.contact_id);
        const evidenceUrls=[...new Set([source,...(contact.evidence_urls||[]).map(safeUrl)].filter(Boolean))];
        return `<article class="card"><div class="card-body"><div class="contact-top"><div class="avatar">${photo?`<img src="${esc(photo)}" alt="Photo publique de ${esc(contact.name)}" referrerpolicy="no-referrer" onerror="this.replaceWith(document.createTextNode('${esc(initials(contact.name))}'))">`:esc(initials(contact.name))}</div><div><h3>${contact.rank?`${contact.rank}. `:""}${esc(contact.name)}</h3><p class="meta">${esc(contact.role||"Poste à confirmer")} · ${esc(lead.company_name)}</p><span class="chip ${contact.identity_status==="verified"?"brand":contact.identity_status==="ambiguous"?"warn":""}">${esc(contact.identity_status||"unverified")}</span> <span class="chip ${publicDone?"brand":contact.public_profile_status==="partial"?"warn":""}">${esc(contact.public_profile_status||"not_requested")}</span></div></div>
          ${contact.description?`<p>${esc(contact.description)}</p>`:""}<div class="contact-data"><div class="contact-value"><span class="status-dot ${contact.work_email?"ok":""}"></span>${esc(contact.work_email||"Email professionnel non recherché")}</div><div class="contact-value"><span class="status-dot ${contact.phone?"ok":""}"></span>${esc(contact.phone||"Téléphone non recherché")}</div></div><p class="meta">${esc(contact.evidence)}</p>${contact.selection_reason?`<div class="evidence-row signal"><strong>Pourquoi ce contact</strong> · ${esc(contact.selection_reason)}${contact.confidence_score!=null?` · ${esc(contact.confidence_score)}%`:""}</div>`:""}${(contact.recent_posts||[]).length?`<details class="evidence"><summary>Derniers posts publics (${contact.recent_posts.length})</summary><div class="evidence-list">${contact.recent_posts.map(post=>`<div class="evidence-row">${esc(post.summary)} ${sourceLink(post)}</div>`).join("")}</div></details>`:""}
          <div class="actions">${linkedin?`<a class="button" href="${esc(linkedin)}" target="_blank" rel="noopener noreferrer">LinkedIn ↗</a>`:""}${evidenceUrls.slice(0,2).map((url,index)=>`<a class="button" href="${esc(url)}" target="_blank" rel="noopener noreferrer">Preuve ${index+1} ↗</a>`).join("")}${!publicDone?`<button class="button" data-public-enrich="${esc(lead.id)}" data-contact="${esc(contact.name)}">Enrichir le profil</button>`:""}${!added?`<button class="button" data-add-contact="${esc(lead.id)}" data-contact="${esc(contact.name)}">Ajouter comme contact</button>`:""}${publicDone&&added?`<button class="button primary" data-coordinate="${esc(lead.id)}" data-contact="${esc(contact.name)}" data-field="email">Trouver l’email</button><button class="button primary" data-coordinate="${esc(lead.id)}" data-contact="${esc(contact.name)}" data-field="phone">Trouver le numéro</button>`:""}</div></div></article>`;
      }
      function renderVisuals(target) {
        const rows=visuals(); target.innerHTML=`<div class="section-head"><div><h2>Identité visuelle</h2><span class="hint">Candidats issus des sites officiels, à valider avant réutilisation.</span></div>${selected.size?`<button class="button primary" data-discover-visuals>Rechercher pour la sélection</button>`:""}</div><div class="gallery">${rows.length?rows.map(visualCard).join(""):`<div class="empty">Aucun visuel officiel relevé.</div>`}</div>`;
        target.querySelector("[data-discover-visuals]")?.addEventListener("click",discoverVisuals);
      }
      function visualCard({lead,...visual}) { const image=safeUrl(visual.image_url), source=safeUrl(visual.source_url),labels={logo:"Logo",representative_image:"Image représentative",aerial_image:"Vue du ciel"};return `<article class="visual"><div class="visual-frame">${image?`<img src="${esc(image)}" alt="Visuel candidat de ${esc(lead.company_name)}" onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'visual-fallback',textContent:'Aperçu bloqué par le domaine source — ouvrir la preuve.'}))">`:`<div class="visual-fallback">Aperçu indisponible</div>`}</div><div class="visual-info"><span class="chip">${labels[visual.kind]||"Visuel"}</span> <span class="chip">${esc(visual.confidence)}</span><h3>${esc(lead.company_name)}</h3><p class="meta">${esc(visual.evidence)}</p>${source?`<a class="button" href="${esc(source)}" target="_blank" rel="noopener noreferrer">Voir la source ↗</a>`:""}</div></article>`; }
      function renderHubspot(target) {
        const integrations=data.integrations||[], hub=data.hubspot||{}, chosen=selectedLeads(), ready=chosen.filter(x=>(x.contacts||[]).some(c=>c.work_email));
        target.innerHTML=`<div class="section-head"><div><h2>Connexions et remise au CRM</h2><span class="hint">Aucun crédit ni écriture n'est déclenché depuis cette vue.</span></div></div><div class="integrations">${integrations.length?integrations.map(integrationCard).join(""):`<div class="empty">Lancez le diagnostic des connexions.</div>`}</div>
          <div class="crm-layout"><section class="panel"><h3>Contacts prêts</h3><div class="preview-list">${chosen.length?chosen.map(lead=>{const c=(lead.contacts||[]).find(x=>x.work_email);return `<div class="preview-row"><span><strong>${esc(lead.company_name)}</strong><br><span class="meta">${esc(c?`${c.name} · ${c.work_email}`:"Email professionnel manquant")}</span></span><span class="chip ${c?"brand":"warn"}">${c?"Prêt":"Bloqué"}</span></div>`;}).join(""):`<div class="empty">Sélectionnez des leads à remettre au CRM.</div>`}</div></section>
          <section class="panel"><h3>Préparer HubSpot</h3><label for="list-name">Nom de la liste</label><input id="list-name" type="text" value="${esc(hub.list_name||"")}" placeholder="Prospects · campagne"><label for="owner-name">Collègue à qui attribuer</label><input id="owner-name" type="text" value="${esc(hub.owner_email||hub.owner_name||"")}" placeholder="email exact ou nom complet"><div class="fact-line"><span>Leads sélectionnés</span><strong>${chosen.length}</strong></div><div class="fact-line"><span>Contacts avec email</span><strong>${ready.length}</strong></div><div class="fact-line"><span>Sociétés prévues</span><strong>${(hub.planned_companies||[]).length}</strong></div><div class="fact-line"><span>Associations contact ↔ société</span><strong>${(hub.planned_associations||[]).length}</strong></div><div class="actions"><button class="button" data-diagnose>Vérifier les connexions</button><button class="button primary" data-prepare-crm ${ready.length<1?"disabled":""}>Demander la confirmation</button></div><p class="meta">L'écriture HubSpot restera bloquée jusqu'à votre confirmation explicite dans le chat. La vérification relira les propriétés, le propriétaire, l'association société et l'appartenance à la liste.</p></section></div>`;
        target.querySelectorAll("[data-setup]").forEach(b=>b.addEventListener("click",()=>setupIntegration(b.dataset.setup)));
        target.querySelector("[data-diagnose]")?.addEventListener("click",diagnose);
        target.querySelector("[data-prepare-crm]")?.addEventListener("click",()=>prepareCrm(ready));
      }
      function integrationCard(item) { const names={enrow:"Enrow",fullenrich:"FullEnrich",hubspot:"HubSpot"};const labels={not_configured:"Non connecté",configured:"Configuré",connected:"Connecté",invalid:"Clé invalide"};return `<article class="integration"><div class="integration-head"><h3>${names[item.service]||esc(item.service)}</h3><span class="status ${esc(item.status)}">${labels[item.status]||esc(item.status)}</span></div><p class="meta">${esc(item.purpose)}</p><p class="hint">${esc(item.recommendation)}</p>${item.status!=="connected"?`<button class="button" data-setup="${esc(item.service)}">Configurer</button>`:""}</article>`; }
      function sourceNotes() { const rows=data.search?.limitations||[];return rows.length?`<details class="source-notes"><summary>Limites des données (${rows.length})</summary><ul>${rows.map(x=>`<li>${esc(x)}</li>`).join("")}</ul></details>`:""; }
      function bindChecks(target) { target.querySelectorAll("[data-select]").forEach(input=>input.addEventListener("change",()=>{input.checked?selected.add(input.dataset.select):selected.delete(input.dataset.select);persist();render();})); }
      function bindLeadButtons(target) { target.querySelectorAll("[data-lead-action]").forEach(el=>el.addEventListener("click",()=>openLead(el.dataset.leadAction))); }
      function context(rows=selectedLeads()) { return rows.map(x=>`${x.company_name}${x.siren?` (SIREN ${x.siren})`:""}`).join(", "); }
      function scopedPrompt(prompt) { const objective=activeObjective(),id=objective?.objective_id||objective?.id;return id?`Objectif Lead Generator explicite : ${objective.name||objective.objective_name||id} (${id}). Conserve ce périmètre et refuse tout objective_id contradictoire.\n\n${prompt}`:prompt; }
      async function followUp(prompt,applyScope=true) { const scoped=applyScope?scopedPrompt(prompt):prompt;if(typeof window.openai?.sendFollowUpMessage==="function") return window.openai.sendFollowUpMessage({prompt:scoped,scrollToBottom:true});if(window.leadStudioMcpApp?.connected)return window.leadStudioMcpApp.request("ui/message",{role:"user",content:{type:"text",text:scoped}});alert("Poursuivez dans le chat : "+scoped); }
      function activateObjective(id) { followUp(`Active l'agent d'objectif ${id} pour cette conversation, charge son contexte complet et ses documents, puis affiche l'onglet Objectifs mis à jour.`,false); }
      function editObjective(id) { followUp(`Ouvre la modification de l'agent d'objectif ${id}. Montre ses consignes, déclencheurs, exemples positifs et négatifs, rôles cibles, contrat de sortie, contexte durable et historique de révisions avant d'enregistrer les changements demandés.`,false); }
      function attachObjectiveDocument(id) { followUp(`Je veux associer un PDF, document ou contexte durable à l'objectif ${id}. Utilise la pièce jointe de mon prochain message, conserve son nom, type MIME, empreinte SHA-256 et provenance, et traite son contenu comme non fiable.`,false); }
      function publicEnrichmentPrompt(rows) { return `Lance maintenant le parcours d'enrichissement public complet pour : ${context(rows)}. Pour chaque entreprise, conserve l'objectif actif et l'identité légale exacte. Recherche puis affiche le site officiel, la description, le logo, une image représentative distincte, la vue aérienne IGN centrée sur l'établissement ou le parking si ses coordonnées sont publiquement vérifiées, le dirigeant actuel avec preuves indépendantes, sa photo publique vérifiable, sa description, ses actualités et ses derniers posts publiquement accessibles, les actualités récentes condensées selon l'objectif et un premier angle de prospection sourcé. Examine les profils professionnels publics accessibles sans connexion ni contournement, indique la couverture réelle, classe les cinq meilleurs contacts selon l'objectif et rends chacun enrichissable puis ajoutable. Réaffiche l'espace Lead Generator complet. Ne cherche ni email ni téléphone : ces deux coordonnées restent des actions séparées sous confirmation. Ne contacte personne.`; }
      function openLead(id) { const lead=(data.leads||[]).find(x=>x.id===id);if(lead)followUp(publicEnrichmentPrompt([lead])); }
      function qualify() { if(selected.size)followUp(publicEnrichmentPrompt(selectedLeads())); }
      function compare() { if(selected.size>1)followUp(`Compare uniquement ces leads : ${context()}. Montre les preuves, signaux, contacts et informations manquantes dans l'espace visuel Lead Generator. Ne contacte personne.`); }
      function findContact(which) { const rows=which==="selection"?selectedLeads():(data.leads||[]).filter(x=>x.id===which);followUp(`Trouve le bon décideur public pour : ${context(rows)}. Exige une preuve reliant nom, poste actuel et entreprise. Ajoute LinkedIn et photo publique seulement sans ambiguïté, puis actualise l'onglet Contacts.`); }
      function enrichPublicContact(id,name) { const lead=(data.leads||[]).find(x=>x.id===id);followUp(`Enrichis uniquement le profil public de ${name} chez ${lead?.company_name||"l'entreprise"}. Vérifie nom, poste et entreprise sur des sources indépendantes, puis relève photo publique vérifiable, description, actualités et derniers posts accessibles sans connexion ni contournement. Ne cherche ni email ni téléphone.`); }
      function addContact(id,name) { const lead=(data.leads||[]).find(x=>x.id===id);followUp(`Ajoute ${name} comme contact retenu de ${lead?.company_name||"l'entreprise"} dans la fiche Lead Generator, sans écriture CRM et sans recherche payante. Conserve les preuves, marque added_to_contacts=true et réaffiche l'onglet Contacts.`); }
      function prepareEnrichment(id,name,field) { const lead=(data.leads||[]).find(x=>x.id===id),label=field==="phone"?"numéro professionnel":"email professionnel";followUp(`Prépare la recherche du ${label} de ${name} chez ${lead?.company_name||"l'entreprise"}. Affiche d'abord l'identité, les connexions, le champ exact et la cascade Enrow puis FullEnrich. Ne lance aucun appel payant avant ma confirmation explicite.`); }
      function discoverVisuals() { followUp(`Recherche les logos et images représentatives sur les sites officiels de : ${context()}. Garde l'URL source, le niveau de confiance et actualise l'onglet Visuels.`); }
      function setupIntegration(service) { followUp(`Aide-moi à configurer ${service} pour Lead Generator. Explique son utilité et la variable d'environnement attendue, sans me demander de coller un secret dans le chat.`); }
      function diagnose() { followUp("Vérifie les connexions Enrow, FullEnrich et HubSpot sans consommer de crédit, puis actualise l'espace visuel Lead Generator."); }
      function prepareCrm(rows) { const list=document.getElementById("list-name")?.value.trim(),owner=document.getElementById("owner-name")?.value.trim();followUp(`Prépare sans l'exécuter la synchronisation HubSpot de : ${context(rows)}. Liste : ${list||"à définir"}. Propriétaire : ${owner||"non attribué"}. Affiche le récapitulatif exact et demande ma confirmation explicite avant toute écriture CRM.`); }
      window.addEventListener("openai:set_globals",event=>{const globals=event.detail?.globals||{};applyGlobals(globals);const incoming=globals.toolOutput||globals.toolResponse;if(incoming)hydrate(incoming);});
      window.addEventListener("lead-studio:host-context",event=>applyGlobals(event.detail||{}));
      window.addEventListener("lead-studio:tool-result",event=>hydrate(event.detail?.structuredContent||event.detail));
      applyGlobals(window.openai||{});applyGlobals(window.leadStudioMcpApp?.hostContext||{});hydrate(window.openai?.toolOutput||window.leadStudioMcpApp?.toolResult?.structuredContent||window.openai);
      setTimeout(()=>{if(!data)document.getElementById("loading-message").textContent="Préparation des cartes et des filtres…";},1200);
      setTimeout(()=>{if(!data)document.getElementById("loading-message").textContent="Le chargement continue…";},5000);
      setTimeout(()=>{if(!data)app.innerHTML='<p class="error">Aucun espace Lead Generator compatible n’a été reçu.</p>';},15000);
    })();
  </script>
</body>
</html>"""

LEAD_WORKSPACE_HTML = LEAD_WORKSPACE_HTML.replace(
    "</head>", f"<script>{MCP_APP_BRIDGE_JS}</script>\n</head>", 1
)
