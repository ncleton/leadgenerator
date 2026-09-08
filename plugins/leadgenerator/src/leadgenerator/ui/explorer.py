"""Self-contained MCP Apps interface for exploring and selecting leads."""

from __future__ import annotations

from leadgenerator.ui.bridge import MCP_APP_BRIDGE_JS

LEAD_EXPLORER_UI_URI = "ui://leadgenerator/lead-explorer/v10.html"
LEAD_EXPLORER_LEGACY_UI_URIS = tuple(
    f"ui://leadgenerator/lead-explorer/v{version}.html" for version in range(1, 10)
)

LEAD_EXPLORER_RESOURCE_META = {
    "ui": {
        "prefersBorder": False,
        "csp": {
            "connectDomains": [],
            "resourceDomains": [
                "https://*",
                "https://tile.openstreetmap.org",
                "https://data.geopf.fr",
                "https://media.licdn.com",
            ],
        },
    },
    "openai/widgetDescription": (
        "Explore des leads sourcés sur une carte ou par code NAF, permet de "
        "constituer une shortlist et d'ouvrir une fiche entreprise."
    ),
    "openai/widgetPrefersBorder": False,
    "openai/widgetCSP": {
        "connect_domains": [],
        "resource_domains": [
            "https://*",
            "https://tile.openstreetmap.org",
            "https://data.geopf.fr",
            "https://media.licdn.com",
        ],
    },
}

LEAD_EXPLORER_TOOL_META = {
    "ui": {"resourceUri": LEAD_EXPLORER_UI_URI},
    "openai/toolInvocation/invoking": (
        "Recherche des entreprises dans le registre officiel…"
    ),
    "openai/toolInvocation/invoked": "Entreprises prêtes à parcourir",
}


LEAD_EXPLORER_HTML = r"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <title>Lead Generator — Explorateur</title>
  <style>
    :root {
      --ink:#142927; --muted:#667774; --paper:#f5f2e9; --surface:#fffdf8;
      --line:#d8ddd5; --brand:#0b6b58; --brand-2:#d7f0e8; --amber:#b36718;
      --hyp:#805b9c; --shadow:0 18px 55px rgba(24,46,42,.13);
      color-scheme:light; font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif;
    }
    :root[data-theme="dark"] {
      --ink:#ecf5f1; --muted:#a9bbb5; --paper:#0e1715; --surface:#17221f;
      --line:#30413c; --brand:#75d7bc; --brand-2:#1f463c; --amber:#efb66f;
      --hyp:#c9a7e6; --shadow:none; color-scheme:dark;
    }
    * { box-sizing:border-box; }
    html,body { margin:0; min-width:0; background:transparent; color:var(--ink); }
    button,a,input { font:inherit; }
    button { color:inherit; }
    #app { min-height:560px; border:1px solid var(--line); border-radius:22px; overflow:hidden;
      background:var(--paper); box-shadow:var(--shadow); }
    .topbar { display:flex; align-items:flex-start; justify-content:space-between; gap:18px;
      padding:18px 20px 14px; background:var(--surface); border-bottom:1px solid var(--line); }
    .eyebrow { margin:0 0 4px; color:var(--brand); font-size:.72rem; font-weight:850;
      letter-spacing:.12em; text-transform:uppercase; }
    h1,h2,h3,p { margin-top:0; }
    h1 { margin-bottom:4px; font-size:clamp(1.25rem,3vw,1.75rem); line-height:1.1; }
    .subtitle { margin:0; color:var(--muted); font-size:.88rem; }
    .summary { display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end; }
    .filter-toggle { display:inline-flex; align-items:center; gap:7px; min-height:30px;
      padding:5px 10px; border:1px solid var(--line); border-radius:999px;
      background:var(--paper); font-size:.78rem; font-weight:740; cursor:pointer; }
    .filter-toggle input { width:16px; height:16px; accent-color:var(--brand); }
    .pill { display:inline-flex; align-items:center; min-height:30px; padding:5px 10px;
      border:1px solid var(--line); border-radius:999px; background:var(--paper); font-size:.78rem; }
    .pill strong { margin-right:4px; }
    .tabs { display:flex; gap:4px; padding:8px 12px; background:var(--surface);
      border-bottom:1px solid var(--line); overflow:auto; }
    .tab { min-height:39px; padding:7px 13px; border:0; border-radius:10px;
      background:transparent; cursor:pointer; font-weight:760; white-space:nowrap; }
    .tab[aria-selected="true"] { color:var(--brand); background:var(--brand-2); }
    .count { display:inline-grid; place-items:center; min-width:21px; height:21px; margin-left:5px;
      border-radius:999px; background:var(--surface); font-size:.7rem; }
    .workspace { position:relative; min-height:470px; }
    .view { display:none; }
    .view.active { display:block; }
    #map-view,#street-map-view { position:relative; min-height:470px; overflow:hidden; background:#dce8df; }
    #street-map-view { min-height:650px; }
    .map-canvas { position:absolute; inset:0; cursor:grab; overflow:hidden; touch-action:none;
      overscroll-behavior:contain; contain:layout paint; }
    .map-canvas.dragging { cursor:grabbing; }
    .tile { position:absolute; width:256px; height:256px; user-select:none; pointer-events:none; }
    .marker { position:absolute; width:34px; height:34px; transform:translate(-50%,-100%);
      border:3px solid var(--surface); border-radius:50% 50% 50% 7px; rotate:-45deg;
      background:var(--brand); box-shadow:0 5px 16px rgba(15,40,35,.32); cursor:pointer; }
    .marker::after { content:""; position:absolute; inset:8px; border-radius:50%;
      background:var(--surface); }
    .marker.selected { background:#d77a24; z-index:3; scale:1.12; }
    .marker.shortlisted::before { content:"✓"; position:absolute; z-index:2; left:9px; top:6px;
      rotate:45deg; color:var(--brand); font-weight:900; font-size:.72rem; }
    .map-controls { position:absolute; z-index:5; top:14px; left:14px; display:grid; gap:6px; }
    .icon-button { width:40px; height:40px; border:1px solid var(--line); border-radius:12px;
      background:var(--surface); box-shadow:0 4px 14px rgba(20,41,39,.12); cursor:pointer;
      font-size:1.1rem; font-weight:800; }
    .map-mode-label { position:absolute; z-index:5; top:14px; left:66px; padding:8px 11px;
      border:1px solid var(--line); border-radius:11px; background:var(--surface);
      box-shadow:0 4px 14px rgba(20,41,39,.12); font-size:.75rem; font-weight:800; }
    .map-loading { position:absolute; z-index:4; inset:0; display:flex; align-items:center;
      justify-content:center; gap:10px; background:color-mix(in srgb,var(--paper) 82%,transparent);
      color:var(--muted); font-size:.84rem; font-weight:700; pointer-events:none; }
    .map-loading[hidden] { display:none; }
    .map-feedback { position:absolute; z-index:5; left:66px; bottom:14px; max-width:min(430px,calc(100% - 92px));
      padding:9px 12px; border:1px solid var(--line); border-radius:11px; background:var(--surface);
      box-shadow:0 4px 14px rgba(20,41,39,.12); font-size:.78rem; font-weight:720; }
    .map-feedback[hidden] { display:none; }
    .map-feedback.error { color:#ad3f36; }
    .user-location-ring { position:absolute; z-index:2; transform:translate(-50%,-50%); border:2px solid rgba(11,107,88,.38);
      border-radius:50%; background:rgba(11,107,88,.11); pointer-events:none; }
    .user-location-marker { position:absolute; z-index:4; width:20px; height:20px; transform:translate(-50%,-50%);
      border:4px solid var(--surface); border-radius:50%; background:#1976d2; box-shadow:0 0 0 2px #1976d2,0 4px 14px rgba(20,41,39,.3); }
    .user-location-marker::after { content:""; position:absolute; inset:-9px; border:2px solid rgba(25,118,210,.42);
      border-radius:50%; animation:location-pulse 1.8s ease-out infinite; }
    @keyframes location-pulse { 0% { transform:scale(.6); opacity:1; } 100% { transform:scale(1.45); opacity:0; } }
    .spinner { display:inline-block; width:22px; height:22px; flex:0 0 auto;
      border:3px solid var(--line); border-top-color:var(--brand); border-radius:50%;
      animation:spin .75s linear infinite; }
    @keyframes spin { to { transform:rotate(360deg); } }
    .map-empty { position:absolute; z-index:4; inset:50% auto auto 50%; transform:translate(-50%,-50%);
      max-width:370px; padding:16px; border:1px solid var(--line); border-radius:15px;
      background:color-mix(in srgb,var(--surface) 94%,transparent); text-align:center; }
    .attribution { position:absolute; right:7px; bottom:5px; z-index:3; padding:3px 6px;
      border-radius:5px; background:rgba(255,255,255,.86); color:#42524f; font-size:.64rem; }
    .attribution a { color:inherit; }
    .drawer { position:absolute; z-index:6; top:14px; right:14px; bottom:14px; width:min(470px,calc(100% - 28px));
      overflow:auto; padding:17px; border:1px solid var(--line); border-radius:18px;
      background:color-mix(in srgb,var(--surface) 97%,transparent); box-shadow:var(--shadow); }
    .drawer[hidden] { display:none; }
    .drawer-close { float:right; width:32px; height:32px; border:0; border-radius:9px;
      background:var(--paper); cursor:pointer; }
    .drawer h2 { margin:5px 36px 4px 0; font-size:1.2rem; }
    .top-actions { display:flex; gap:8px; margin:10px 38px 13px 0; }
    .top-actions .button { flex:1; }
    .company-hero { position:relative; height:150px; margin:0 0 12px; overflow:hidden;
      border:1px solid var(--line); border-radius:14px; background:var(--paper); }
    .company-hero>img { width:100%; height:100%; object-fit:cover; }
    .company-hero .hero-fallback { display:grid; place-items:center; height:100%; color:var(--muted); }
    .company-logo { position:absolute; right:10px; top:10px; width:72px; height:54px; padding:7px;
      border:1px solid rgba(0,0,0,.12); border-radius:10px; background:rgba(255,255,255,.94); object-fit:contain!important; }
    .aerial { position:relative; overflow:hidden; border:1px solid var(--line); border-radius:14px; background:var(--paper); }
    .aerial img { display:block; width:100%; aspect-ratio:8/5; object-fit:cover; }
    .aerial-reticle { position:absolute; left:50%; top:50%; width:28px; height:28px; transform:translate(-50%,-50%);
      border:2px solid white; border-radius:50%; box-shadow:0 0 0 2px rgba(11,107,88,.9),0 2px 9px rgba(0,0,0,.4); }
    .aerial-reticle::before,.aerial-reticle::after { content:""; position:absolute; background:white; }
    .aerial-reticle::before { left:12px; top:-7px; width:2px; height:38px; }
    .aerial-reticle::after { left:-7px; top:12px; width:38px; height:2px; }
    .aerial-caption { padding:9px 10px; color:var(--muted); font-size:.75rem; }
    .angle { padding:12px; border-left:4px solid var(--brand); border-radius:0 12px 12px 0; background:var(--brand-2); }
    .person { display:grid; grid-template-columns:48px minmax(0,1fr); gap:10px; padding:10px;
      border:1px solid var(--line); border-radius:12px; background:var(--paper); }
    .person-avatar { width:48px; height:48px; display:grid; place-items:center; overflow:hidden;
      border-radius:50%; background:var(--brand-2); font-weight:850; }
    .person-avatar img { width:100%; height:100%; object-fit:cover; }
    .person h3 { margin:0 0 2px; font-size:.9rem; }
    .person p { margin:0; }
    .person .actions { grid-column:1/-1; margin-top:4px; }
    .compact-button { min-height:34px; padding:6px 9px; font-size:.74rem; }
    .news-row { padding:10px; border:1px solid var(--line); border-radius:11px; background:var(--paper); }
    .news-row h3 { margin:0 0 4px; font-size:.85rem; }
    .meta { color:var(--muted); font-size:.8rem; }
    .location { margin:12px 0; padding:10px 12px; border-left:3px solid var(--brand);
      background:var(--brand-2); border-radius:0 10px 10px 0; font-size:.84rem; }
    .section { padding-top:13px; margin-top:13px; border-top:1px solid var(--line); }
    .section-title { display:flex; align-items:center; justify-content:space-between; gap:8px;
      margin-bottom:9px; font-size:.77rem; text-transform:uppercase; letter-spacing:.07em; font-weight:850; }
    .fact-list { display:grid; gap:7px; }
    .fact { padding:9px 10px; border:1px solid var(--line); border-radius:11px; background:var(--paper);
      color:inherit; text-decoration:none; }
    .fact strong,.fact span { display:block; }
    .fact strong { font-size:.76rem; color:var(--muted); margin-bottom:2px; }
    .fact span { font-size:.86rem; }
    .signal { border-left:3px solid var(--brand); }
    .hypothesis { border-left:3px solid var(--hyp); }
    .actions { display:flex; flex-wrap:wrap; gap:8px; margin-top:15px; }
    .button { display:inline-flex; align-items:center; justify-content:center; min-height:40px; padding:8px 13px;
      border:1px solid var(--line); border-radius:11px; background:var(--surface); color:var(--ink);
      text-decoration:none; cursor:pointer; font-weight:760; }
    .button.primary { border-color:var(--brand); background:var(--brand); color:white; }
    :root[data-theme="dark"] .button.primary { color:#10201c; }
    .button:disabled { opacity:.45; cursor:not-allowed; }
    .list-shell { padding:16px; }
    .list-head { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap;
      gap:10px; margin-bottom:12px; }
    .list-head h2 { margin:0; font-size:1.05rem; }
    .lead-list { display:grid; gap:9px; }
    .lead-row { display:grid; grid-template-columns:auto minmax(0,1fr) auto; align-items:center; gap:12px;
      padding:12px 13px; border:1px solid var(--line); border-radius:14px; background:var(--surface); }
    .check { width:20px; height:20px; accent-color:var(--brand); cursor:pointer; }
    .lead-main { min-width:0; cursor:pointer; }
    .lead-main h3 { margin:0 0 3px; font-size:.96rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .lead-main p { margin:0; color:var(--muted); font-size:.78rem; white-space:nowrap;
      overflow:hidden; text-overflow:ellipsis; }
    .status-chip { padding:5px 8px; border-radius:999px; background:var(--brand-2);
      color:var(--brand); font-size:.7rem; font-weight:780; }
    .shortlist-empty { padding:44px 18px; border:1px dashed var(--line); border-radius:15px;
      color:var(--muted); text-align:center; background:var(--surface); }
    .shortlist-bar { position:sticky; bottom:0; display:flex; align-items:center; justify-content:space-between;
      gap:10px; padding:12px 16px; border-top:1px solid var(--line); background:var(--surface); }
    .shortlist-actions { display:flex; flex-wrap:wrap; gap:7px; justify-content:flex-end; }
    .loading { min-height:560px; display:flex; align-items:center; justify-content:center;
      gap:12px; padding:32px; color:var(--muted); text-align:center; }
    .error { padding:32px; color:var(--muted); }
    .error { color:#ad3f36; }
    :root[data-display-mode="fullscreen"] body { width:100vw; height:100dvh; overflow:hidden; }
    :root[data-display-mode="fullscreen"] #app { width:100vw; height:100dvh; min-height:100dvh;
      border:0; border-radius:0; box-shadow:none; }
    :root[data-display-mode="fullscreen"] .topbar,
    :root[data-display-mode="fullscreen"] .tabs,
    :root[data-display-mode="fullscreen"] .shortlist-bar { display:none; }
    :root[data-display-mode="fullscreen"] .workspace,
    :root[data-display-mode="fullscreen"] #map-view,
    :root[data-display-mode="fullscreen"] #street-map-view { height:100dvh; min-height:100dvh; }
    @media (max-width:700px) {
      #app { border-radius:16px; min-height:620px; }
      .topbar { padding:15px; display:block; }
      .summary { justify-content:flex-start; margin-top:11px; }
      .workspace,#map-view { min-height:515px; }
      #street-map-view { min-height:680px; }
      .drawer { top:auto; max-height:64%; }
      .lead-row { grid-template-columns:auto minmax(0,1fr); }
      .status-chip { grid-column:2; justify-self:start; }
      .shortlist-bar { align-items:flex-start; flex-direction:column; }
      .shortlist-actions { justify-content:flex-start; }
    }
    @media (prefers-reduced-motion:reduce) {
      * { scroll-behavior:auto!important; transition:none!important; }
      .spinner { animation:none; }
      .user-location-marker::after { animation:none; }
    }
  </style>
</head>
<body>
  <main id="app"><div class="loading" role="status" aria-live="polite"><span class="spinner" aria-hidden="true"></span><span id="loading-message">Chargement de Lead Generator…</span></div></main>
  <script>
    (() => {
      "use strict";
      const app = document.getElementById("app");
      let data = null, dataFingerprint = null, activeView = "map", activeLeadId = null;
      let selected = new Set(), headquartersOnly = false;
      const mapStates = {
        map: { lat:46.6, lon:2.5, zoom:5 },
        street_map: { lat:50.6292, lon:3.0573, zoom:16 },
      };
      let streetMapInitialized = false;
      let userLocation = null;
      let locationRequestPending = false;
      let drag = null;
      let mapRenderId = 0;
      const mapRenderFrames = { map: 0, street_map: 0 };
      const wheelGestures = {
        map: { delta:0, direction:0, lastInputAt:0, cooldownUntil:0, frame:0, x:0, y:0 },
        street_map: { delta:0, direction:0, lastInputAt:0, cooldownUntil:0, frame:0, x:0, y:0 },
      };
      const WHEEL_ZOOM_THRESHOLD = 120;
      const WHEEL_ZOOM_COOLDOWN_MS = 140;
      const WHEEL_GESTURE_IDLE_MS = 240;

      const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({
        "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
      })[char]);
      const safeUrl = value => {
        try { const url = new URL(String(value || "")); return ["http:","https:"].includes(url.protocol) ? url.href : null; }
        catch { return null; }
      };
      const leadById = id => data?.leads?.find(lead => lead.id === id);
      const visibleLeads = () => (data?.leads || []).filter(lead =>
        !headquartersOnly || lead?.location_is_headquarters === true);
      const employeeBand = lead => lead?.employee_band_label ||
        (lead?.observed_facts || []).find(fact => /effectif/i.test(fact.label || ""))?.value || null;
      const mappedLeads = () => visibleLeads().filter(lead =>
        Number.isFinite(lead?.location?.latitude) && Number.isFinite(lead?.location?.longitude));
      const labelForView = view => view === "naf_list" ? "Code NAF" : view === "shortlist" ? "Sélection" : view === "street_map" ? "Carte détaillée" : "Carte";
      const mapElementId = view => view === "street_map" ? "street-map" : "map";
      const drawerElementId = view => view === "street_map" ? "street-drawer" : "drawer";
      const isMapView = view => view === "map" || view === "street_map";

      function extractPayload(value) {
        if (!value) return null;
        if (value.kind === "lead_explorer") return value;
        if (value.structuredContent?.kind === "lead_explorer") return value.structuredContent;
        if (value.structured_content?.kind === "lead_explorer") return value.structured_content;
        if (value.output?.kind === "lead_explorer") return value.output;
        return null;
      }

      function applyHostGlobals(globals) {
        const theme = globals?.theme || window.openai?.theme;
        if (theme) document.documentElement.dataset.theme = theme === "dark" ? "dark" : "light";
        const displayMode = globals?.displayMode || window.openai?.displayMode;
        if (displayMode) setDisplayMode(displayMode);
      }

      function hydrate(incoming) {
        const payload = extractPayload(incoming);
        if (!payload || !Array.isArray(payload.leads)) return;
        const fingerprint = JSON.stringify(payload);
        if (fingerprint === dataFingerprint) return;
        dataFingerprint = fingerprint;
        data = payload;
        const saved = window.openai?.widgetState || {};
        const allowedIds = new Set(data.leads.map(lead => lead.id));
        const savedIds = Array.isArray(saved.selectedLeadIds) ? saved.selectedLeadIds : data.selected_ids || [];
        selected = new Set(savedIds.filter(id => allowedIds.has(id)));
        headquartersOnly = typeof data.headquarters_only === "boolean" ? data.headquarters_only :
          typeof saved.headquartersOnly === "boolean" ? saved.headquartersOnly :
          Boolean(data.search_details?.applied_filters?.headquarters_only);
        const requested = saved.activeView || data.initial_view || "map";
        activeView = ["map","street_map","naf_list","shortlist"].includes(requested) ? requested : "map";
        renderShell();
      }

      function persistState() {
        const state = { activeView, selectedLeadIds:[...selected], activeLeadId, headquartersOnly };
        if (typeof window.openai?.setWidgetState === "function") {
          Promise.resolve(window.openai.setWidgetState(state)).catch(() => undefined);
        }
      }

      function renderShell() {
        const query = data.naf_query || {};
        const visible = visibleLeads();
        const mapped = mappedLeads().length;
        const total = headquartersOnly ? visible.length.toLocaleString("fr-FR") :
          Number.isFinite(query.total_results) ? query.total_results.toLocaleString("fr-FR") : visible.length;
        app.innerHTML = `
          <header class="topbar">
            <div><p class="eyebrow">Lead Generator · exploration humaine</p>
              <h1>${query.code ? `Entreprises · ${esc(query.code)}` : "Carte des leads"}</h1>
              <p class="subtitle">${query.label ? esc(query.label) : "Faits publics, hypothèses séparées et sélection sans envoi automatique."}</p></div>
            <div class="summary"><span class="pill"><strong>${esc(total)}</strong> résultat${total === "1" ? "" : "s"}</span>
              <span class="pill"><strong>${mapped}</strong> cartographié${mapped === 1 ? "" : "s"}</span>
              <label class="filter-toggle"><input id="headquarters-only" type="checkbox" ${headquartersOnly ? "checked" : ""}> Siège uniquement</label></div>
          </header>
          <nav class="tabs" aria-label="Vues des leads">
            ${tabButton("map","Carte",mapped)}
            ${tabButton("street_map","Carte détaillée",mapped)}
            ${tabButton("naf_list", query.code ? `NAF ${esc(query.code)}` : "Liste", visible.length)}
            ${tabButton("shortlist","Sélection",selected.size)}
          </nav>
          <section class="workspace">
            <section id="map-view" class="view" aria-label="Carte des leads">
              <div id="map" class="map-canvas" data-map-view="map" aria-label="Carte OpenStreetMap d’ensemble"></div>
              <div class="map-controls"><button class="icon-button" data-map="in" data-map-view="map" aria-label="Zoom avant">+</button>
                <button class="icon-button" data-map="out" data-map-view="map" aria-label="Zoom arrière">−</button>
                <button class="icon-button" data-map="fit" data-map-view="map" aria-label="Afficher tous les leads">⌖</button>
                <button class="icon-button" data-map="locate" data-map-view="map" aria-label="Détecter ma position" title="Détecter ma position">◎</button>
                <button class="icon-button" data-map="fullscreen" data-map-view="map" aria-label="Afficher la carte en plein écran" title="Afficher la carte en plein écran">⛶</button></div>
              <div id="map-feedback" class="map-feedback" role="status" aria-live="polite" hidden></div>
              <a class="attribution" href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">© OpenStreetMap contributors</a>
              <aside id="drawer" class="drawer" hidden></aside>
            </section>
            <section id="street-map-view" class="view" aria-label="Carte OpenStreetMap détaillée">
              <div id="street-map" class="map-canvas" data-map-view="street_map" aria-label="Carte OpenStreetMap détaillée jusqu’aux rues"></div>
              <div class="map-controls"><button class="icon-button" data-map="in" data-map-view="street_map" aria-label="Zoom avant sur la carte détaillée">+</button>
                <button class="icon-button" data-map="out" data-map-view="street_map" aria-label="Zoom arrière sur la carte détaillée">−</button>
                <button class="icon-button" data-map="focus" data-map-view="street_map" aria-label="Recentrer sur un lead">⌖</button>
                <button class="icon-button" data-map="locate" data-map-view="street_map" aria-label="Détecter ma position" title="Détecter ma position">◎</button>
                <button class="icon-button" data-map="fullscreen" data-map-view="street_map" aria-label="Afficher la carte en plein écran" title="Afficher la carte en plein écran">⛶</button></div>
              <div class="map-mode-label">Vue rues · OpenStreetMap</div>
              <div id="street-map-feedback" class="map-feedback" role="status" aria-live="polite" hidden></div>
              <a class="attribution" href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">© OpenStreetMap contributors</a>
              <aside id="street-drawer" class="drawer" hidden></aside>
            </section>
            <section id="naf-list-view" class="view list-shell"></section>
            <section id="shortlist-view" class="view list-shell"></section>
          </section>
          <footer class="shortlist-bar"><span><strong id="selected-count">${selected.size}</strong> lead${selected.size === 1 ? "" : "s"} retenu${selected.size === 1 ? "" : "s"}</span>
            <div class="shortlist-actions"><button class="button" data-action="compare" ${selected.size < 2 ? "disabled" : ""}>Comparer</button>
              <button class="button primary" data-action="qualify" ${selected.size < 1 ? "disabled" : ""}>Enrichir la sélection</button></div></footer>`;
        bindShell();
        switchView(activeView, false);
        if (activeView === "map") {
          if (mapped) fitMap("map"); else renderMap("map");
        }
      }

      function tabButton(id, label, count) {
        return `<button class="tab" data-view="${id}" aria-selected="${activeView === id}">${label}<span class="count">${count}</span></button>`;
      }

      function bindShell() {
        app.querySelectorAll("[data-view]").forEach(button => button.addEventListener("click", () => switchView(button.dataset.view)));
        app.querySelectorAll("[data-map]").forEach(button => button.addEventListener("click", () => {
          const view = button.dataset.mapView;
          const state = mapStates[view];
          if (button.dataset.map === "fit") fitMap(view);
          else if (button.dataset.map === "focus") focusStreetMap();
          else if (button.dataset.map === "locate") locateUser(view);
          else if (button.dataset.map === "fullscreen") toggleFullscreen(view);
          else setMapZoom(view, state.zoom + (button.dataset.map === "in" ? 1 : -1));
        }));
        app.querySelector("[data-action='compare']")?.addEventListener("click", compareSelection);
        app.querySelector("[data-action='qualify']")?.addEventListener("click", qualifySelection);
        app.querySelector("#headquarters-only")?.addEventListener("change", event => {
          headquartersOnly = event.currentTarget.checked;
          activeLeadId = null;
          persistState();
          renderShell();
          followUp(`Relance exactement la dernière recherche Lead Generator depuis la page 1 avec headquarters_only=${headquartersOnly}. Conserve sans les modifier tous les autres filtres (NAF, zone géographique, effectifs, catégorie et exclusions), puis réaffiche l'explorateur. Par défaut, place les établissements actifs réellement situés dans la zone ; si headquarters_only=true, conserve uniquement les sièges qui satisfont eux-mêmes la zone et l'activité.`);
        });
        app.querySelectorAll(".map-canvas").forEach(map => {
          map.addEventListener("pointerdown", startDrag);
          map.addEventListener("pointermove", moveDrag);
          map.addEventListener("pointerup", endDrag);
          map.addEventListener("pointercancel", endDrag);
          map.addEventListener("wheel", handleMapWheel, {passive:false});
        });
      }

      function switchView(view, save=true) {
        activeView = view;
        app.querySelectorAll(".view").forEach(item => item.classList.remove("active"));
        const targetId = view === "naf_list" ? "naf-list-view" : `${view.replace("_", "-")}-view`;
        document.getElementById(targetId)?.classList.add("active");
        app.querySelectorAll(".tab").forEach(button => button.setAttribute("aria-selected", String(button.dataset.view === view)));
        if (view === "naf_list") renderList(visibleLeads(), "naf-list-view");
        if (view === "shortlist") renderList(visibleLeads().filter(lead => selected.has(lead.id)), "shortlist-view", true);
        if (view === "street_map") initializeStreetMap();
        if (isMapView(view)) setTimeout(() => renderMap(view),0);
        if (save) persistState();
      }

      function renderList(leads, targetId, shortlistedOnly=false) {
        const target = document.getElementById(targetId);
        if (!target) return;
        const query = data.naf_query || {};
        target.innerHTML = `<div class="list-head"><h2>${shortlistedOnly ? "Votre sélection" : query.code ? `Code NAF ${esc(query.code)}` : "Tous les leads"}</h2>
          <span class="meta">${leads.length} affiché${leads.length === 1 ? "" : "s"}${query.page ? ` · page ${query.page}` : ""}</span></div>
          <div class="lead-list">${leads.length ? leads.map(leadRow).join("") : `<div class="shortlist-empty">${shortlistedOnly ? "Cochez des entreprises dans la liste ou sur la carte pour les retrouver ici." : "Aucune entreprise dans cette page."}</div>`}</div>`;
        target.querySelectorAll(".check").forEach(input => input.addEventListener("change", () => toggleLead(input.dataset.id, input.checked)));
        target.querySelectorAll(".lead-main").forEach(item => item.addEventListener("click", () => openLead(item.dataset.id)));
      }

      function leadRow(lead) {
        const place = lead.location?.label || "Localisation à enrichir";
        const status = lead.website_url ? "Site identifié" : "À qualifier";
        const workforce = employeeBand(lead);
        return `<article class="lead-row"><input class="check" data-id="${esc(lead.id)}" type="checkbox" ${selected.has(lead.id) ? "checked" : ""} aria-label="Sélectionner ${esc(lead.company_name)}">
          <div class="lead-main" data-id="${esc(lead.id)}" tabindex="0" role="button"><h3>${esc(lead.company_name)}</h3>
            <p>${esc(lead.naf_code || lead.activity || "Activité à confirmer")}${workforce ? ` · ${esc(workforce)}` : ""} · ${esc(place)}</p></div>
          <span class="status-chip">${status}</span></article>`;
      }

      function toggleLead(id, checked) {
        if (checked) selected.add(id); else selected.delete(id);
        persistState();
        renderShell();
        if (activeLeadId) showDrawer(activeLeadId);
      }

      function openLead(id) {
        activeLeadId = id;
        if (activeView !== "map") switchView("map");
        const lead = leadById(id);
        if (lead?.location && Number.isFinite(lead.location.latitude)) {
          const state = mapStates.map;
          state.lat = lead.location.latitude; state.lon = lead.location.longitude; state.zoom = Math.max(state.zoom, 11); renderMap("map");
        }
        showDrawer(id, "map"); persistState();
      }

      function showDrawer(id, view=activeView) {
        const lead = leadById(id), drawer = document.getElementById(drawerElementId(view));
        if (!lead || !drawer) return;
        const website = safeUrl(lead.website_url), profile = safeUrl(lead.legal_profile_url);
        drawer.hidden = false;
        const representative=safeUrl(lead.representative_image_url), logo=safeUrl(lead.logo_url);
        drawer.innerHTML = `<button class="drawer-close" aria-label="Fermer">×</button>
          <p class="eyebrow">Fiche lead · ${selected.has(id) ? "retenu" : "à examiner"}</p>
          <div class="top-actions"><button class="button ${selected.has(id) ? "" : "primary"}" data-select>${selected.has(id) ? "Retirer de la sélection" : "Ajouter à la sélection"}</button><button class="button" data-full>Enrichir</button></div>
          ${representative||logo?`<div class="company-hero">${representative?`<img src="${esc(representative)}" alt="Image représentative de ${esc(lead.company_name)}">`:`<div class="hero-fallback">Image représentative non trouvée</div>`}${logo?`<img class="company-logo" src="${esc(logo)}" alt="Logo de ${esc(lead.company_name)}">`:""}</div>`:""}
          <h2>${esc(lead.company_name)}</h2>
          <p class="meta">${lead.siren ? `SIREN ${esc(lead.siren)} · ` : ""}${esc(lead.naf_code || "NAF à confirmer")}</p>
          ${lead.company_description?`<p>${esc(lead.company_description)}</p>`:""}
          ${lead.location ? `<div class="location"><strong>Localisation publique</strong><br>${esc(lead.location.label)}<br><span class="meta">${lead.location.precision === "unavailable" ? "Coordonnées non disponibles" : "Coordonnées issues de la source indiquée"}</span></div>` : ""}
          ${aerialSection(lead)}${directorSection(lead.director)}${newsSection(lead)}${angleSection(lead)}${contactsSection(lead)}
          ${factsSection(lead.observed_facts)}${signalsSection(lead.opportunity_signals)}${hypothesesSection(lead.hypotheses_to_validate)}
          ${lead.missing_information?.length ? `<section class="section"><div class="section-title">À enrichir</div><div class="fact-list">${lead.missing_information.map(value => `<div class="fact"><span>${esc(value)}</span></div>`).join("")}</div></section>` : ""}
          <div class="actions">${website ? `<a class="button" href="${esc(website)}" target="_blank" rel="noopener noreferrer">Voir le site ↗</a>` : ""}
            ${profile ? `<a class="button" href="${esc(profile)}" target="_blank" rel="noopener noreferrer">Fiche officielle ↗</a>` : ""}
          </div>`;
        drawer.querySelector(".drawer-close").addEventListener("click", () => { drawer.hidden = true; activeLeadId = null; renderMap(view); persistState(); });
        drawer.querySelector("[data-select]").addEventListener("click", () => toggleLead(id, !selected.has(id)));
        drawer.querySelector("[data-full]").addEventListener("click", () => askForFullProfile(lead));
        drawer.querySelectorAll("[data-public-profile]").forEach(button=>button.addEventListener("click",()=>enrichPublicProfile(lead,button.dataset.publicProfile)));
        drawer.querySelectorAll("[data-add-contact]").forEach(button=>button.addEventListener("click",()=>addContact(lead,button.dataset.addContact)));
        drawer.querySelectorAll("[data-coordinate]").forEach(button=>button.addEventListener("click",()=>findCoordinate(lead,button.dataset.coordinate,button.dataset.field)));
      }

      function aerialSection(lead) {
        const image=safeUrl(lead.aerial_image_url), source=safeUrl(lead.aerial_source_url);
        if(!image)return "";
        const focus=lead.aerial_focus||lead.location;
        return `<section class="section"><div class="section-title">Vue du ciel · parking et emprise</div><div class="aerial"><img src="${esc(image)}" alt="Orthophoto centrée sur ${esc(focus?.label||lead.company_name)}"><span class="aerial-reticle" aria-hidden="true"></span><div class="aerial-caption">Centrée automatiquement sur ${esc(focus?.label||"les coordonnées publiques de l’établissement")}. ${focus?.precision==="official_address_coordinates"?"Point issu de l’adresse officielle.":"Centrage à contrôler."} ${source?`<a href="${esc(source)}" target="_blank" rel="noopener noreferrer">Source IGN ↗</a>`:""}</div></div></section>`;
      }
      function directorSection(director) {
        if(!director)return "";
        return `<section class="section"><div class="section-title">Dirigeant identifié</div>${personCard(director,true)}</section>`;
      }
      function newsSection(lead) {
        const rows=lead.recent_news||[];if(!rows.length&&!lead.news_summary)return "";
        return `<section class="section"><div class="section-title">Actualité utile <span>${rows.length}</span></div>${lead.news_summary?`<p>${esc(lead.news_summary)}</p>`:""}<div class="fact-list">${rows.map(item=>`<article class="news-row"><h3>${esc(item.title)}</h3><p>${esc(item.summary)}</p>${item.relevance?`<p class="meta">Intérêt commercial · ${esc(item.relevance)}</p>`:""}<a href="${esc(safeUrl(item.source_url)||"#")}" target="_blank" rel="noopener noreferrer">${esc(item.published_at||"Source")} ↗</a></article>`).join("")}</div></section>`;
      }
      function angleSection(lead) {
        if(!lead.outreach_angle)return "";
        const sources=(lead.outreach_angle_source_urls||[]).map(safeUrl).filter(Boolean);
        return `<section class="section"><div class="section-title">Premier angle de prospection</div><div class="angle">${esc(lead.outreach_angle)}${sources.length?`<div class="actions">${sources.map((url,index)=>`<a class="button compact-button" href="${esc(url)}" target="_blank" rel="noopener noreferrer">Source ${index+1} ↗</a>`).join("")}</div>`:""}</div></section>`;
      }
      function contactsSection(lead) {
        const rows=(lead.contacts||[]).slice().sort((a,b)=>(a.rank||99)-(b.rank||99)).slice(0,5);
        if(!rows.length)return "";
        const coverage=lead.public_profiles_discovered==null?"":`${lead.public_profiles_reviewed||0}/${lead.public_profiles_discovered} profils publics examinés`;
        return `<section class="section"><div class="section-title">5 meilleurs contacts <span>${rows.length}</span></div>${coverage?`<p class="meta">${esc(coverage)}${lead.public_profile_coverage_note?` · ${esc(lead.public_profile_coverage_note)}`:""}</p>`:""}<div class="fact-list">${rows.map(person=>personCard(person,false)).join("")}</div></section>`;
      }
      function personCard(person,isDirector=false) {
        const photo=safeUrl(person.profile_image_url), linkedin=safeUrl(person.linkedin_url), evidence=[person.source_url,...(person.evidence_urls||[])].map(safeUrl).filter(Boolean);
        const initials=person.name.split(/\s+/).filter(Boolean).map(x=>x[0]).slice(0,2).join("").toUpperCase();
        const publicDone=person.public_profile_status==="complete", added=Boolean(person.added_to_contacts||person.contact_id);
        const posts=person.recent_posts||[], news=person.recent_news||[];
        return `<article class="person"><div class="person-avatar">${photo?`<img src="${esc(photo)}" alt="Photo publique de ${esc(person.name)}">`:esc(initials)}</div><div><h3>${person.rank?`${person.rank}. `:""}${esc(person.name)}</h3><p class="meta">${esc(person.role||"Poste à confirmer")}</p>${person.description?`<p>${esc(person.description)}</p>`:""}${person.selection_reason?`<p class="meta">Pourquoi · ${esc(person.selection_reason)}</p>`:""}</div>${posts.length||news.length?`<details class="evidence" style="grid-column:1/-1"><summary>Actualité et derniers posts publics (${posts.length+news.length})</summary><div class="evidence-list">${posts.map(item=>`<a class="fact" href="${esc(safeUrl(item.source_url)||"#")}" target="_blank" rel="noopener noreferrer"><strong>${esc(item.published_at||item.platform||"Post public")}</strong><span>${esc(item.summary)}</span></a>`).join("")}${news.map(item=>`<a class="fact" href="${esc(safeUrl(item.source_url)||"#")}" target="_blank" rel="noopener noreferrer"><strong>${esc(item.title)}</strong><span>${esc(item.summary)}</span></a>`).join("")}</div></details>`:""}<div class="actions">${linkedin?`<a class="button compact-button" href="${esc(linkedin)}" target="_blank" rel="noopener noreferrer">LinkedIn ↗</a>`:""}${evidence.slice(0,2).map((url,index)=>`<a class="button compact-button" href="${esc(url)}" target="_blank" rel="noopener noreferrer">Preuve ${index+1} ↗</a>`).join("")}${!publicDone?`<button class="button compact-button" data-public-profile="${esc(person.name)}">Enrichir le profil</button>`:""}${!isDirector&&!added?`<button class="button compact-button" data-add-contact="${esc(person.name)}">Ajouter comme contact</button>`:""}${publicDone&&added?`<button class="button primary compact-button" data-coordinate="${esc(person.name)}" data-field="email">Trouver l’email</button><button class="button primary compact-button" data-coordinate="${esc(person.name)}" data-field="phone">Trouver le numéro</button>`:""}</div></article>`;
      }

      function factsSection(facts=[]) {
        if (!facts.length) return "";
        return `<section class="section"><div class="section-title">Faits observés <span>${facts.length}</span></div><div class="fact-list">${facts.map(fact => `<a class="fact" href="${esc(safeUrl(fact.source_url) || "#")}" target="_blank" rel="noopener noreferrer"><strong>${esc(fact.label)}</strong><span>${esc(fact.value)}</span></a>`).join("")}</div></section>`;
      }
      function signalsSection(signals=[]) {
        if (!signals.length) return "";
        return `<section class="section"><div class="section-title">Signaux sourcés <span>${signals.length}</span></div><div class="fact-list">${signals.map(item => `<a class="fact signal" href="${esc(safeUrl(item.source_url) || "#")}" target="_blank" rel="noopener noreferrer"><strong>${esc(item.signal)}</strong><span>${esc(item.evidence)}</span></a>`).join("")}</div></section>`;
      }
      function hypothesesSection(items=[]) {
        if (!items.length) return "";
        return `<section class="section"><div class="section-title">Hypothèses à valider <span>${items.length}</span></div><div class="fact-list">${items.map(item => `<div class="fact hypothesis"><strong>${esc(item.hypothesis)}</strong><span>${esc(item.rationale)}</span></div>`).join("")}</div></section>`;
      }

      function worldPoint(lat, lon, zoom) {
        const scale = 256 * 2 ** zoom, clipped = Math.max(-85.0511, Math.min(85.0511, lat));
        const sin = Math.sin(clipped * Math.PI / 180);
        return { x:(lon + 180) / 360 * scale, y:(.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * scale };
      }
      function latLonFromWorld(x,y,zoom) {
        const scale = 256 * 2 ** zoom, lon = x / scale * 360 - 180, n = Math.PI - 2 * Math.PI * y / scale;
        return { lon, lat:180 / Math.PI * Math.atan(.5 * (Math.exp(n) - Math.exp(-n))) };
      }
      function scheduleMapRender(view) {
        if (!isMapView(view) || mapRenderFrames[view]) return;
        mapRenderFrames[view] = requestAnimationFrame(() => {
          mapRenderFrames[view] = 0;
          renderMap(view);
        });
      }
      function setMapZoom(view, nextZoom, anchorX=null, anchorY=null) {
        const state=mapStates[view], map=document.getElementById(mapElementId(view));
        if(!state||!map)return;
        const zoom=Math.max(2,Math.min(19,nextZoom));
        if(zoom===state.zoom)return;
        const w=map.clientWidth,h=map.clientHeight;
        const x=Number.isFinite(anchorX)?Math.max(0,Math.min(w,anchorX)):w/2;
        const y=Number.isFinite(anchorY)?Math.max(0,Math.min(h,anchorY)):h/2;
        const center=worldPoint(state.lat,state.lon,state.zoom);
        const anchor=latLonFromWorld(center.x+x-w/2,center.y+y-h/2,state.zoom);
        const zoomedAnchor=worldPoint(anchor.lat,anchor.lon,zoom);
        const zoomedCenter={x:zoomedAnchor.x-(x-w/2),y:zoomedAnchor.y-(y-h/2)};
        Object.assign(state,latLonFromWorld(zoomedCenter.x,zoomedCenter.y,zoom),{zoom});
        renderMap(view);
      }
      function normalizedWheelDelta(event, map) {
        const multiplier=event.deltaMode===1?16:event.deltaMode===2?Math.max(1,map.clientHeight):1;
        return Math.max(-WHEEL_ZOOM_THRESHOLD,Math.min(WHEEL_ZOOM_THRESHOLD,event.deltaY*multiplier));
      }
      function handleMapWheel(event) {
        event.preventDefault();
        const map=event.currentTarget,view=map.dataset.mapView,gesture=wheelGestures[view];
        const delta=normalizedWheelDelta(event,map),direction=Math.sign(delta);
        if(!direction)return;
        const now=event.timeStamp;
        if((gesture.direction&&gesture.direction!==direction)||now-gesture.lastInputAt>WHEEL_GESTURE_IDLE_MS)gesture.delta=0;
        gesture.delta+=delta; gesture.direction=direction; gesture.lastInputAt=now;
        const rect=map.getBoundingClientRect();
        gesture.x=event.clientX-rect.left; gesture.y=event.clientY-rect.top;
        if(!gesture.frame)gesture.frame=requestAnimationFrame(()=>commitWheelZoom(view));
      }
      function commitWheelZoom(view) {
        const gesture=wheelGestures[view]; gesture.frame=0;
        const now=performance.now();
        if(now<gesture.cooldownUntil){gesture.delta=0;return;}
        if(Math.abs(gesture.delta)<WHEEL_ZOOM_THRESHOLD)return;
        const step=gesture.delta<0?1:-1;
        gesture.delta=0; gesture.cooldownUntil=now+WHEEL_ZOOM_COOLDOWN_MS;
        setMapZoom(view,mapStates[view].zoom+step,gesture.x,gesture.y);
      }
      function renderMap(view=activeView) {
        if (!isMapView(view)) return;
        const state = mapStates[view], map = document.getElementById(mapElementId(view));
        if (!map || !map.offsetWidth) return;
        const showLoading=map.dataset.ready!=="true";
        map.replaceChildren();
        const renderId = ++mapRenderId;
        const loading = showLoading?document.createElement("div"):null;
        if(loading){
          loading.className = "map-loading";
          loading.setAttribute("role", "status");
          loading.innerHTML = '<span class="spinner" aria-hidden="true"></span><span>Chargement de la carte…</span>';
          map.append(loading);
        }
        const w=map.clientWidth,h=map.clientHeight, center=worldPoint(state.lat,state.lon,state.zoom);
        const startX=Math.floor((center.x-w/2)/256), endX=Math.floor((center.x+w/2)/256);
        const startY=Math.floor((center.y-h/2)/256), endY=Math.floor((center.y+h/2)/256), max=2**state.zoom;
        let tileCount=0, settledTiles=0;
        const settleTile = loaded => {
          if(renderId!==mapRenderId) return;
          settledTiles += 1;
          if(loaded || settledTiles>=tileCount){if(loading)loading.hidden=true;map.dataset.ready="true";}
        };
        for(let x=startX;x<=endX;x++) for(let y=startY;y<=endY;y++) {
          if(y<0||y>=max) continue; const tile=document.createElement("img"); tile.className="tile"; tile.alt=""; tile.draggable=false;
          tileCount += 1; tile.decoding="async"; tile.addEventListener("load",()=>settleTile(true),{once:true}); tile.addEventListener("error",()=>settleTile(false),{once:true});
          tile.src=`https://tile.openstreetmap.org/${state.zoom}/${((x%max)+max)%max}/${y}.png`;
          tile.style.left=`${x*256-(center.x-w/2)}px`; tile.style.top=`${y*256-(center.y-h/2)}px`; map.append(tile);
        }
        for(const lead of mappedLeads()) {
          const point=worldPoint(lead.location.latitude,lead.location.longitude,state.zoom), button=document.createElement("button");
          button.className=`marker${lead.id===activeLeadId?" selected":""}${selected.has(lead.id)?" shortlisted":""}`;
          button.style.left=`${point.x-(center.x-w/2)}px`; button.style.top=`${point.y-(center.y-h/2)}px`;
          button.setAttribute("aria-label",`Voir ${lead.company_name}`); button.addEventListener("click", event => { event.stopPropagation(); activeLeadId=lead.id; renderMap(view); showDrawer(lead.id,view); persistState(); }); map.append(button);
        }
        if(userLocation) renderUserLocation(map,state,center,w,h);
        if(!tileCount){if(loading)loading.hidden=true;map.dataset.ready="true";}
        if(loading)setTimeout(()=>{if(renderId===mapRenderId){loading.hidden=true;map.dataset.ready="true";}},2500);
        if(!mappedLeads().length) { if(loading)loading.hidden=true; map.dataset.ready="true"; const empty=document.createElement("div"); empty.className="map-empty"; empty.innerHTML="<strong>Aucune coordonnée sourcée</strong><br><span class='meta'>Les entreprises restent disponibles dans la vue liste. La carte ne place jamais une adresse au hasard.</span>"; map.append(empty); }
      }
      function fitMap(view="map") {
        const points=mappedLeads(); if(!points.length){renderMap(view);return;}
        const state=mapStates[view];
        const lats=points.map(l=>l.location.latitude),lons=points.map(l=>l.location.longitude);
        state.lat=(Math.min(...lats)+Math.max(...lats))/2; state.lon=(Math.min(...lons)+Math.max(...lons))/2;
        const map=document.getElementById(mapElementId(view)), width=Math.max(300,map?.clientWidth||800), height=Math.max(280,map?.clientHeight||470);
        for(let z=15;z>=2;z--){const nw=worldPoint(Math.max(...lats),Math.min(...lons),z),se=worldPoint(Math.min(...lats),Math.max(...lons),z);if(se.x-nw.x<width-110&&se.y-nw.y<height-110){state.zoom=z;break;}}
        renderMap(view);
      }
      function initializeStreetMap() {
        if (streetMapInitialized) return;
        const points=mappedLeads();
        const lead=leadById(activeLeadId) || points.find(item=>selected.has(item.id)) || points[0];
        if(lead?.location) Object.assign(mapStates.street_map,{lat:lead.location.latitude,lon:lead.location.longitude,zoom:16});
        streetMapInitialized=true;
      }
      function focusStreetMap() {
        streetMapInitialized=false;
        initializeStreetMap();
        mapStates.street_map.zoom=Math.max(mapStates.street_map.zoom,16);
        renderMap("street_map");
      }
      function feedbackElement(view) { return document.getElementById(view === "street_map" ? "street-map-feedback" : "map-feedback"); }
      function setLocationFeedback(view,message,error=false) {
        const feedback=feedbackElement(view); if(!feedback)return;
        feedback.hidden=!message; feedback.textContent=message||""; feedback.classList.toggle("error",error);
      }
      function updateLocationControls() {
        app.querySelectorAll('[data-map="locate"]').forEach(button => {
          button.disabled=locationRequestPending;
          button.textContent=locationRequestPending?"…":"◎";
          button.setAttribute("aria-busy",String(locationRequestPending));
        });
      }
      function geolocationErrorMessage(error) {
        if(error?.code===1)return "Localisation refusée. Autorisez-la dans les réglages du navigateur pour vous positionner sur la carte.";
        if(error?.code===2)return "Position indisponible. Vérifiez que la localisation de l’appareil est activée.";
        if(error?.code===3)return "La détection de position a expiré. Réessayez dans un endroit mieux couvert.";
        return "Impossible de détecter votre position sur cet appareil.";
      }
      function locateUser(view=activeView) {
        if(locationRequestPending)return;
        if(!navigator.geolocation) { setLocationFeedback(view,"La détection de position n’est pas disponible dans cet environnement.",true); return; }
        locationRequestPending=true; updateLocationControls();
        setLocationFeedback(view,"Détection de votre position…");
        navigator.geolocation.getCurrentPosition(position => {
          locationRequestPending=false;
          userLocation={lat:position.coords.latitude,lon:position.coords.longitude,accuracy:Math.max(0,position.coords.accuracy||0)};
          const state=mapStates[view]; Object.assign(state,{lat:userLocation.lat,lon:userLocation.lon,zoom:Math.max(state.zoom,14)});
          updateLocationControls(); renderMap(view);
          const precision=userLocation.accuracy?` · précision ${Math.round(userLocation.accuracy)} m`:"";
          setLocationFeedback(view,`Votre position est affichée${precision}. Elle reste uniquement dans cette carte.`);
        }, error => {
          locationRequestPending=false; updateLocationControls(); setLocationFeedback(view,geolocationErrorMessage(error),true);
        }, {enableHighAccuracy:true,timeout:10000,maximumAge:60000});
      }
      function renderUserLocation(map,state,center,width,height) {
        const point=worldPoint(userLocation.lat,userLocation.lon,state.zoom);
        const left=point.x-(center.x-width/2),top=point.y-(center.y-height/2);
        const metersPerPixel=Math.max(.01,156543.03392*Math.cos(userLocation.lat*Math.PI/180)/(2**state.zoom));
        const radius=Math.max(12,Math.min(160,userLocation.accuracy/metersPerPixel));
        const ring=document.createElement("div"); ring.className="user-location-ring";
        ring.style.left=`${left}px`; ring.style.top=`${top}px`; ring.style.width=`${radius*2}px`; ring.style.height=`${radius*2}px`; map.append(ring);
        const marker=document.createElement("div"); marker.className="user-location-marker";
        marker.style.left=`${left}px`; marker.style.top=`${top}px`; marker.setAttribute("role","img");
        marker.setAttribute("aria-label",`Votre position${userLocation.accuracy?`, précision ${Math.round(userLocation.accuracy)} mètres`:""}`); map.append(marker);
      }
      function setDisplayMode(mode) {
        const normalized=mode==="fullscreen"?"fullscreen":"inline";
        document.documentElement.dataset.displayMode=normalized;
        app.querySelectorAll('[data-map="fullscreen"]').forEach(button => {
          const expanded=normalized==="fullscreen";
          const label=expanded?"Quitter le plein écran":"Afficher la carte en plein écran";
          button.textContent=expanded?"✕":"⛶"; button.setAttribute("aria-label",label); button.title=label;
        });
        if(isMapView(activeView))setTimeout(()=>scheduleMapRender(activeView),0);
      }
      async function toggleFullscreen(view=activeView) {
        if(activeView!==view)switchView(view);
        const expanded=document.documentElement.dataset.displayMode==="fullscreen"||Boolean(document.fullscreenElement);
        const target=expanded?"inline":"fullscreen";
        try {
          if(typeof window.openai?.requestDisplayMode==="function") {
            const result=await window.openai.requestDisplayMode({mode:target});
            setDisplayMode(result?.mode||target); return;
          }
          if(window.leadGeneratorMcpApp?.connected) {
            const result=await window.leadGeneratorMcpApp.request("ui/request-display-mode",{mode:target});
            setDisplayMode(result?.mode||target); return;
          }
          if(target==="fullscreen"&&document.documentElement.requestFullscreen)await document.documentElement.requestFullscreen();
          else if(target==="inline"&&document.fullscreenElement&&document.exitFullscreen)await document.exitFullscreen();
          else throw new Error("fullscreen unavailable");
          setDisplayMode(target);
        } catch {
          setLocationFeedback(view,"Le plein écran n’est pas disponible dans cet environnement.",true);
        }
      }
      function startDrag(event) {
        if(event.target.closest("button"))return;
        const map=event.currentTarget, view=map.dataset.mapView, state=mapStates[view];
        drag={view,x:event.clientX,y:event.clientY,center:worldPoint(state.lat,state.lon,state.zoom)};
        map.setPointerCapture(event.pointerId); map.classList.add("dragging");
      }
      function moveDrag(event) {
        if(!drag)return;
        const state=mapStates[drag.view], point={x:drag.center.x-(event.clientX-drag.x),y:drag.center.y-(event.clientY-drag.y)};
        Object.assign(state,latLonFromWorld(point.x,point.y,state.zoom)); scheduleMapRender(drag.view);
      }
      function endDrag(event) { drag=null; event.currentTarget?.classList.remove("dragging"); }

      async function followUp(prompt) {
        const scoped=data?.objective_id?`Objectif Lead Generator explicite : ${data.objective_id}. Conserve ce périmètre et refuse tout objective_id contradictoire.\n\n${prompt}`:prompt;
        if(typeof window.openai?.sendFollowUpMessage === "function") {
          await window.openai.sendFollowUpMessage({prompt:scoped,scrollToBottom:true}); return;
        }
        if(window.leadGeneratorMcpApp?.connected) {
          await window.leadGeneratorMcpApp.request("ui/message",{role:"user",content:{type:"text",text:scoped}}); return;
        }
        alert("Poursuivez dans le chat : " + scoped);
      }
      function selectedContext() { return [...selected].map(id => {const lead=leadById(id);return lead?`${lead.company_name}${lead.siren?` (SIREN ${lead.siren})`:""}`:null;}).filter(Boolean).join(", "); }
      function publicEnrichmentPrompt(rows) {
        const companies=rows.map(lead=>`${lead.company_name}${lead.siren?` (SIREN ${lead.siren})`:""}`).join(", ");
        return `Lance maintenant le parcours d'enrichissement public complet pour : ${companies}. Pour chaque entreprise, conserve l'objectif actif et l'identité légale exacte, puis récupère et affiche dans Lead Generator : le site officiel et la description, le logo officiel, une image représentative de l'entreprise distincte du logo, la vue aérienne IGN centrée sur l'établissement ou le parking quand ses coordonnées publiques sont plus précises, le dirigeant actuel avec preuves indépendantes, sa photo publique vérifiable, sa description, ses actualités et ses derniers posts publiquement accessibles, les actualités récentes de l'entreprise condensées en fonction de l'objectif, et un premier angle de prospection sourcé. Recherche les profils professionnels publics de l'entreprise sans connexion ni contournement, indique la couverture réellement obtenue, classe les cinq meilleurs contacts selon l'objectif, et rends chacun enrichissable et ajoutable comme contact. Termine en réaffichant la fiche interactive complète. Ne lance aucune recherche payante d'email ou de téléphone : après l'enrichissement public, ces deux actions doivent rester les seules coordonnées à rechercher. Ne contacte personne.`;
      }
      function qualifySelection() { if(selected.size) followUp(publicEnrichmentPrompt(data.leads.filter(lead=>selected.has(lead.id)))); }
      function compareSelection() { if(selected.size>1) followUp(`Compare uniquement ces leads sélectionnés : ${selectedContext()}. Classe les faits sourcés, les signaux commerciaux et les informations manquantes séparément. Termine par une recommandation à valider humainement, sans envoyer de message.`); }
      function askForFullProfile(lead) { followUp(publicEnrichmentPrompt([lead])); }
      function enrichPublicProfile(lead,name) { followUp(`Enrichis uniquement le profil public de ${name} chez ${lead.company_name}. Vérifie le nom, le poste actuel et l'entreprise sur des sources indépendantes, puis relève sa photo publique vérifiable, sa description, ses actualités et ses derniers posts accessibles sans connexion ni contournement. Réaffiche la fiche avec public_profile_status à complete seulement si les éléments sont réellement sourcés. Ne cherche ni email ni téléphone.`); }
      function addContact(lead,name) { followUp(`Ajoute ${name} comme contact retenu de ${lead.company_name} dans la fiche Lead Generator, sans écriture CRM et sans recherche payante. Conserve toutes les preuves publiques, marque added_to_contacts=true, puis réaffiche la fiche.`); }
      function findCoordinate(lead,name,field) { const label=field==="phone"?"numéro professionnel":"email professionnel";followUp(`Prépare la recherche du ${label} de ${name} chez ${lead.company_name}. Vérifie d'abord l'identité publique, affiche la cascade Enrow puis FullEnrich, les crédits potentiels et le champ exact. Ne transmets rien et ne dépense aucun crédit avant ma confirmation explicite dans le chat.`); }

      window.addEventListener("resize", () => isMapView(activeView) && scheduleMapRender(activeView));
      document.addEventListener("fullscreenchange", () => setDisplayMode(document.fullscreenElement?"fullscreen":"inline"));
      window.addEventListener("openai:set_globals", event => { const globals=event.detail?.globals||{}; applyHostGlobals(globals); const incoming=globals.toolOutput||globals.toolResponse; if(incoming)hydrate(incoming); });
      window.addEventListener("leadgenerator:host-context", event => applyHostGlobals(event.detail||{}));
      window.addEventListener("leadgenerator:tool-result", event => hydrate(event.detail?.structuredContent||event.detail));
      applyHostGlobals(window.openai||{});
      applyHostGlobals(window.leadGeneratorMcpApp?.hostContext||{});
      hydrate(window.openai?.toolOutput||window.leadGeneratorMcpApp?.toolResult?.structuredContent||window.openai);
      setTimeout(() => { if(!data) document.getElementById("loading-message").textContent="Recherche des entreprises en cours…"; },1200);
      setTimeout(() => { if(!data) document.getElementById("loading-message").textContent="La recherche prend un peu plus de temps, mais elle continue…"; },5000);
    })();
  </script>
</body>
</html>"""

LEAD_EXPLORER_HTML = LEAD_EXPLORER_HTML.replace(
    "</head>", f"<script>{MCP_APP_BRIDGE_JS}</script>\n</head>", 1
)
