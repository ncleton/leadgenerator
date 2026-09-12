"""MCP Apps workspace for the complete human-reviewed lead workflow."""

from __future__ import annotations

from leadgenerator.ui.aerial import AERIAL_VIEW_CSS, AERIAL_VIEW_JS
from leadgenerator.ui.bridge import MCP_APP_BRIDGE_JS
from leadgenerator.ui.objective_management import OBJECTIVE_MANAGEMENT_JS

LEAD_WORKSPACE_UI_URI = "ui://leadgenerator/lead-workspace/v18.html"
LEAD_WORKSPACE_LEGACY_UI_URIS = tuple(
    f"ui://leadgenerator/lead-workspace/v{version}.html" for version in range(1, 18)
)

LEAD_WORKSPACE_RESOURCE_META = {
    "ui": {
        "prefersBorder": False,
        "csp": {
            "connectDomains": [],
            "resourceDomains": [
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
    .header { position:relative; padding:14px 16px 10px; background:var(--surface); border-bottom:1px solid var(--line); }
    .head-row { display:flex; align-items:center; justify-content:space-between; gap:24px; }
    .header-tools { display:flex; align-items:center; gap:10px; flex:0 0 auto; }
    .header-copy { min-width:0; max-width:720px; padding-right:94px; }
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
    .fullscreen-button { position:absolute; top:10px; right:10px; min-height:28px; padding:4px 7px; border:1px solid var(--line); border-radius:7px;
      background:var(--paper); color:var(--ink); cursor:pointer; font-size:.76rem; font-weight:780; white-space:nowrap; }
    .fullscreen-button .fullscreen-icon { margin-right:6px; font-size:1rem; }
    .fullscreen-exit { display:none; position:fixed; z-index:100; top:16px; right:16px; min-height:42px;
      padding:8px 13px; border:1px solid var(--line); border-radius:12px; background:var(--surface);
      color:var(--ink); box-shadow:var(--shadow); cursor:pointer; font-weight:800; }
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
    .tabs { display:grid; grid-template-columns:repeat(auto-fit,minmax(105px,1fr)); gap:4px; padding:8px 12px; background:var(--surface);
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
    .contact-company { margin-bottom:24px; border-top:1px solid var(--line); padding-top:16px; }
    .linkedin-connection { margin-bottom:14px; }
    .linkedin-connection .section-head { flex-wrap:wrap; margin:0; }
    .linkedin-connection .section-head>div { flex:1 1 220px; min-width:0; }
    .linkedin-connection h3 { margin-bottom:6px; }
    .linkedin-connection p { margin:0; }
    .linkedin-connection button { flex:0 0 auto; }
    .contact-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:10px; align-items:start; }
    .card { position:relative; overflow:hidden; border:1px solid var(--line); border-radius:16px; background:var(--surface); }
    .company-card { display:grid; grid-template-columns:minmax(220px,29%) minmax(0,1fr); align-items:start; }
    .company-card.no-media { grid-template-columns:minmax(0,1fr); }
    .company-media { min-width:0; border-right:1px solid var(--line); background:var(--surface-2); }
    .cover { position:relative; height:174px; display:grid; place-items:center; overflow:hidden;
      border-bottom:1px solid var(--line); background:linear-gradient(145deg,var(--brand-soft),var(--surface-2)); }
    .cover>img:not(.company-logo) { position:absolute; inset:0; width:100%; height:100%; object-fit:cover; }
    .company-identity { display:flex; align-items:center; gap:10px; min-width:0; margin-bottom:7px; }
    .company-identity>div { min-width:0; }
    .company-identity .meta { margin:0; }
    .company-logo { display:grid; place-items:center; flex:0 0 112px; width:112px; height:42px; padding:5px;
      border:1px solid #d8ddd5; border-radius:7px; background:#fff; object-fit:contain; }
    .company-logo>img { display:block; max-width:100%; width:100%; height:100%; min-height:0; object-fit:contain; }
    .company-logo-initials { font-size:20px; color:var(--brand); font-weight:850; }
    .company-logo:not([data-logo-state="missing"]):not([data-logo-state="error"]) .company-logo-initials { display:none; }
    .intel-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:9px; margin-top:10px; }
    .intel-block { min-width:0; padding:10px 11px; border:1px solid var(--line); border-radius:11px; background:var(--paper); }
    .intel-block h4 { margin:0 0 6px; font-size:.74rem; text-transform:uppercase; letter-spacing:.05em; }
    .intel-block p { margin:0; font-size:.76rem; }
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
    .button.danger { border-color:color-mix(in srgb,var(--danger) 42%,var(--line)); color:var(--danger); background:var(--danger-soft); }
    :root[data-theme="dark"] .button.primary { color:#10201c; }
    .button:disabled { opacity:.45; cursor:not-allowed; }
    .brand-logo { display:block; max-width:160px; max-height:44px; object-fit:contain; margin-bottom:8px; }
    .declarative-grid { display:grid; gap:12px; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); }
    .declarative-panel { border:1px solid var(--line); border-radius:14px; padding:16px; background:var(--surface); }
    .declarative-panel pre { white-space:pre-wrap; overflow-wrap:anywhere; font-size:12px; color:var(--muted); }
    :root[data-density="compact"] { font-size:14px; }
    :root[data-density="compact"] .header { padding:10px 12px 8px; }
    :root[data-density="compact"] .head-row { display:block; }
    :root[data-density="compact"] h1 { font-size:18px; margin-bottom:4px; }
    :root[data-density="compact"] .eyebrow { font-size:10px; margin-bottom:3px; }
    :root[data-density="compact"] .sub { font-size:11px; line-height:1.3; }
    :root[data-density="compact"] .header-tools { margin-top:6px; }
    :root[data-density="compact"] .metrics { display:flex; gap:12px; margin:0; }
    :root[data-density="compact"] .metric { display:flex; align-items:baseline; gap:4px; min-width:0; padding:0; border:0; background:none; }
    :root[data-density="compact"] .metric strong { font-size:12px; }
    :root[data-density="compact"] .metric span { margin:0; font-size:10px; text-transform:none; letter-spacing:0; }
    :root[data-density="compact"] .brief { margin-top:6px; }
    :root[data-density="compact"] .brief>summary { padding:3px 7px; font-size:11px; }
    :root[data-density="compact"] .tabs { padding:4px 7px; gap:2px; }
    :root[data-density="compact"] .tab { min-height:28px; padding:4px 7px; font-size:12px; border-radius:6px; }
    :root[data-density="compact"] .badge { min-width:16px; height:16px; margin-left:3px; font-size:10px; }
    :root[data-density="compact"] .main { padding:10px; min-height:300px; }
    :root[data-density="compact"] .section-head { margin-bottom:8px; gap:8px; }
    :root[data-density="compact"] .section-head h2 { font-size:14px; }
    :root[data-density="compact"] .hint,:root[data-density="compact"] .meta { font-size:11px; }
    :root[data-density="compact"] .company-grid { gap:9px; }
    :root[data-density="compact"] .company-card { grid-template-columns:minmax(120px,20%) minmax(0,1fr); }
    :root[data-density="compact"] .card { border-radius:10px; }
    :root[data-density="compact"] .card-body,:root[data-density="compact"] .declarative-panel { padding:10px; font-size:12px; }
    :root[data-density="compact"] .company-card h3 { font-size:14px; }
    :root[data-density="compact"] .cover { height:104px; }
    :root[data-density="compact"] .company-description { margin:6px 0; font-size:12px; line-height:1.4; }
    :root[data-density="compact"] .fact-line { padding:4px 0; font-size:11px; }
    :root[data-density="compact"] .intel-grid { gap:6px; margin-top:7px; }
    :root[data-density="compact"] .intel-block { padding:7px; }
    :root[data-density="compact"] .intel-block h4 { font-size:10px; margin-bottom:4px; }
    :root[data-density="compact"] .intel-block p { font-size:11px; line-height:1.4; }
    :root[data-density="compact"] .evidence { padding:6px 7px; margin-top:6px; border-radius:7px; }
    :root[data-density="compact"] .evidence summary { font-size:11px; }
    :root[data-density="compact"] .evidence-row { padding:6px; font-size:11px; }
    :root[data-density="compact"] .actions { gap:4px; margin-top:7px; }
    :root[data-density="compact"] .button { min-height:26px; padding:4px 7px; font-size:11px; border-radius:6px; }
    :root[data-density="compact"] .chip { min-height:20px; padding:2px 6px; font-size:10px; }
    :root[data-density="compact"] .avatar { flex:0 0 40px; width:40px; height:40px; border-radius:10px; margin:0; }
    :root[data-density="compact"] .contact-top { gap:8px; }
    :root[data-density="compact"] .contact-top h3 { font-size:13px; line-height:1.25; margin:0 0 3px; }
    :root[data-density="compact"] .contact-top .meta { margin:3px 0; }
    :root[data-density="compact"] .contact-card .card-body { display:flex; flex-direction:column; }
    :root[data-density="compact"] .contact-card .contact-top { order:-2; }
    :root[data-density="compact"] .contact-card .card-body>.actions { order:-1; margin:7px 0; }
    :root[data-density="compact"] .contact-grid { grid-template-columns:repeat(auto-fill,minmax(250px,1fr)); gap:7px; }
    :root[data-density="compact"] .contact-company { margin-bottom:14px; padding-top:10px; }
    :root[data-density="compact"] .contact-data { margin-top:6px; padding:6px; }
    :root[data-density="compact"] .contact-value { min-height:20px; font-size:11px; }
    :root[data-density="compact"] .footer { padding:7px 10px; font-size:11px; }
    .avatar { position:relative; width:62px; height:62px; display:grid; place-items:center; margin-bottom:10px;
      overflow:hidden; border:2px solid var(--surface); border-radius:18px; background:var(--brand-soft);
      color:var(--brand); font-weight:900; font-size:1.2rem; }
    .avatar img { position:absolute; inset:0; width:100%; height:100%; object-fit:cover; }
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
    input[type="text"],input[type="search"],input[type="number"],input[type="time"],select,textarea { width:100%; min-height:40px; padding:8px 10px; color:var(--ink);
      border:1px solid var(--line); border-radius:10px; background:var(--paper); }
    textarea,select { font:inherit; font-size:.8rem; }
    textarea { resize:vertical; }
    input[type="file"] { max-width:100%; font-size:.78rem; }
    .objective-editor-layout { display:grid; grid-template-columns:minmax(0,1.3fr) minmax(0,1fr); gap:14px; }
    .objective-editor-layout>section { min-width:0; }
    .objective-editor-layout details { margin-top:12px; }
    .objective-editor-layout summary { cursor:pointer; font-size:.8rem; }
    .objective-example { margin:10px 0; padding:10px; border:1px solid var(--line); border-radius:10px; }
    .document-hash { overflow-wrap:anywhere; font-size:.7rem; }
    .objective-note { white-space:pre-wrap; overflow-wrap:anywhere; font-size:.8rem; }
    .schedule-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:0 12px; }
    .weekdays { display:flex; gap:12px; flex-wrap:wrap; }
    .checkbox-label { display:flex; align-items:center; gap:7px; }
    .checkbox-label input { accent-color:var(--brand); }
    fieldset { margin-top:12px; border:1px solid var(--line); border-radius:10px; }
    legend { color:var(--muted); font-size:.75rem; }
    @media(max-width:760px) { .objective-editor-layout { grid-template-columns:1fr; } }
    .settings-layout { display:grid; grid-template-columns:minmax(0,1fr); gap:16px; }
    .settings-preferences { max-width:520px; }
    .form-feedback { min-height:20px; margin:8px 0 0; color:var(--muted); font-size:.74rem; }
    .form-feedback.error { padding:0; color:var(--danger); }
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
    :root[data-display-mode="fullscreen"] body { width:100vw; height:100dvh; overflow:hidden; background:var(--paper); }
    :root[data-display-mode="fullscreen"] #app { width:100vw; height:100dvh; min-height:100dvh;
      overflow:hidden; border:0; border-radius:0; box-shadow:none; }
    :root[data-display-mode="fullscreen"] .header,
    :root[data-display-mode="fullscreen"] .tabs,
    :root[data-display-mode="fullscreen"] .footer { display:none; }
    :root[data-display-mode="fullscreen"] .main { height:100dvh; min-height:100dvh; overflow:auto;
      padding:68px 24px 28px; }
    :root[data-display-mode="fullscreen"] .fullscreen-exit { display:inline-flex; align-items:center; justify-content:center; }
    @media(max-width:760px) {
      #app { border-radius:16px; min-height:620px; }
      .head-row,.footer { align-items:flex-start; flex-direction:column; }
      .header-tools { width:100%; align-items:flex-start; flex-direction:column; }
      .metrics { width:100%; margin-top:6px; }
      .fullscreen-button { width:auto; }
      .tabs { grid-template-columns:repeat(3,minmax(0,1fr)); }
      .main { padding:11px; }
      .pipeline { grid-template-columns:repeat(4,250px); }
      .company-card { grid-template-columns:1fr; }
      .company-media { border-right:0; border-bottom:1px solid var(--line); }
      .cover { height:150px; }
      .intel-grid,.company-facts { grid-template-columns:1fr; }
      .crm-layout { grid-template-columns:1fr; }
      .footer-actions { justify-content:flex-start; }
      :root[data-display-mode="fullscreen"] .main { padding:64px 11px 18px; }
    }
    @media(max-width:580px) {
      :root[data-density="compact"] .company-card { grid-template-columns:1fr; }
      :root[data-density="compact"] .company-media { display:grid; grid-template-columns:1fr 1fr; }
      :root[data-density="compact"] .company-media>*:only-child { grid-column:1/-1; }
      :root[data-density="compact"] .cover { height:82px; border:0; }
      :root[data-density="compact"] .company-logo { flex-basis:92px; width:92px; height:36px; }
      :root[data-density="compact"] .intel-grid { grid-template-columns:1fr 1fr; }
      :root[data-density="compact"] .company-facts { grid-template-columns:1fr 1fr; gap:0 9px; }
      :root[data-density="compact"] .contact-grid { grid-template-columns:1fr; }
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
      const uiConfig = () => data?.ui||{};
      const navConfig = () => uiConfig().navigation||{};
      const customTabs = () => Array.isArray(uiConfig().tabs)?uiConfig().tabs:[];
      const actionSelectors = {
        "objectives.create":"[data-create-objective]","objectives.delete":"[data-delete-objective]","leads.compare":"[data-global='compare']","leads.enrich-selection":"[data-global='qualify']",
        "company.refresh":"[data-lead-action]","company.view-contacts":"[data-show-contacts]","contacts.find":"[data-find-contact]","contacts.enrich-public":"[data-public-enrich]",
        "contacts.add":"[data-add-contact]","contacts.find-email":"[data-coordinate][data-field='email']","contacts.find-phone":"[data-coordinate][data-field='phone']",
        "visuals.discover":"[data-discover-visuals]","integrations.check":"[data-diagnose]","crm.hubspot.prepare":"[data-prepare-crm]"
      };
      function applyUiTheme() {
        const theme=uiConfig().theme||{},root=document.documentElement;
        if(/^#[0-9a-f]{6}$/i.test(theme.primary_color||"")) root.style.setProperty("--brand",theme.primary_color);
        if(/^#[0-9a-f]{6}$/i.test(theme.surface_color||"")) root.style.setProperty("--surface",theme.surface_color);
        root.dataset.density=theme.density||"comfortable";
        root.style.fontFamily=theme.font_family==="editorial"?'Georgia,"Times New Roman",serif':"Inter,ui-sans-serif,system-ui,-apple-system,sans-serif";
      }
      function applyVisibility(root=document) {
        for(const [id,label] of Object.entries(uiConfig().visibility?.action_labels||{})) root.querySelectorAll(actionSelectors[id]||"[data-never-match]").forEach(node=>node.textContent=String(label));
        for(const id of uiConfig().visibility?.hidden_actions||[]) root.querySelectorAll(actionSelectors[id]||"[data-never-match]").forEach(node=>{node.hidden=true;node.style.display="none";});
        for(const id of uiConfig().visibility?.hidden_panels||[]) root.querySelectorAll(`[data-panel-id="${CSS.escape(id)}"]`).forEach(node=>{node.hidden=true;node.style.display="none";});
      }
      function tabRows(all) {
        const counts={objectives:objectives().length,pipeline:all.length,companies:all.length,contacts:contacts().length,visuals:visuals().length,settings:null};
        const labels={objectives:"Objectifs",pipeline:"Pipeline",companies:"Entreprises",contacts:"Contacts",visuals:"Visuels",hubspot:"HubSpot",settings:"Réglages",...(navConfig().labels||{})};
        const hidden=new Set(navConfig().hidden||[]),custom=customTabs().map(row=>({id:row.tab_id,label:row.label,count:(row.panels||[]).length,order:row.order??100}));
        const management=data?.management_only||data?.initial_view==="objectives";
        const allowed=id=>management?["objectives","settings"].includes(id):id!=="objectives";
        const native=Object.keys(counts).filter(allowed).map((id,index)=>({id,label:labels[id]||id,count:counts[id],order:index*10}));
        const merged=[...native.filter(row=>!custom.some(item=>item.id===row.id)),...custom.filter(row=>allowed(row.id))].filter(row=>!hidden.has(row.id));
        const explicit=navConfig().order||[]; return merged.sort((a,b)=>{const ai=explicit.indexOf(a.id),bi=explicit.indexOf(b.id);if(ai>=0||bi>=0)return (ai<0?999:ai)-(bi<0?999:bi);return a.order-b.order;});
      }
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
        return window.leadGeneratorMcpApp.extractPayload(value,"lead_workspace");
      }
      function applyGlobals(globals) {
        const theme=globals?.theme||window.openai?.theme;
        if(theme) document.documentElement.dataset.theme=theme==="dark"?"dark":"light";
        const displayMode=globals?.displayMode||window.openai?.displayMode;
        setDisplayMode(displayMode || document.documentElement.dataset.displayMode);
      }
      let contactCompanyId="";
      function hydrate(incoming) {
        const payload=extractPayload(incoming); if(!payload||!Array.isArray(payload.leads)) return;
        const fingerprint=JSON.stringify(payload); if(fingerprint===dataFingerprint) return;
        dataFingerprint=fingerprint;
        data=payload; const saved=window.leadGeneratorMcpApp.loadState("workspace",data);
        applyUiTheme();
        const ids=new Set(data.leads.map(lead=>lead.id));
        selected=new Set((saved.selectedLeadIds||data.selected_ids||[]).filter(id=>ids.has(id)));
        const available=tabRows(data.leads||[]).map(row=>row.id),previous=data.initial_view||saved.activeView||navConfig().default_tab,requested=previous==="hubspot"?"settings":previous;
        activeView=available.includes(requested)?requested:(available.includes(navConfig().default_tab)?navConfig().default_tab:available[0]||"pipeline");
        searchText=String(saved.searchText||"");
        contactCompanyId=ids.has(saved.contactCompanyId)?saved.contactCompanyId:""; render();
      }
      function persist() {
        window.leadGeneratorMcpApp.saveState("workspace",data,{activeView,selectedLeadIds:[...selected],searchText,contactCompanyId});
      }
      function render() {
        const all=data.leads||[], foundContacts=contacts().filter(x=>x.work_email||x.phone).length;
        const objective=activeObjective();
        const filters=visibleFilters(Object.entries(data.search?.filters||{}).filter(([,v])=>v!==null&&v!==""&&(!Array.isArray(v)||v.length)));
        const title=data.management_only?"Objectifs et planifications":all.length?`${all.length} entreprise${all.length===1?"":"s"} qualifiée${all.length===1?"":"s"}`:"Pipeline de prospection";
        const configuredTabs=tabRows(all),logo=uiConfig().logo_data_url;
        app.innerHTML=`<header class="header"><div class="head-row"><div class="header-copy">${logo?`<img class="brand-logo" src="${esc(logo)}" alt="Logo">`:""}<p class="eyebrow">Lead Generator</p>
          <h1>${esc(title)}</h1><p class="sub">${objective?`${esc(objective.agent?.emoji||"🎯")} ${esc(objective.agent?.name||objective.name||objective.objective_name||objective.objective_id)}`:"Assistant général"} · recherche professionnelle sourcée, sous validation humaine.</p></div>
          <div class="header-tools"><div class="metrics"><div class="metric"><strong>${all.length}</strong><span>entreprises</span></div><div class="metric"><strong>${contacts().length}</strong><span>contacts</span></div><div class="metric"><strong>${foundContacts}</strong><span>coordonnées</span></div></div></div></div><button class="fullscreen-button" data-fullscreen aria-label="Agrandir la vue en plein écran" title="Agrandir la vue en plein écran"><span class="fullscreen-icon" aria-hidden="true">⛶</span>Agrandir</button>
          <details class="brief"><summary>Voir le périmètre et les limites</summary><div class="brief-body">${data.search?.summary?`<p>${esc(data.search.summary)}</p>`:""}<div class="filters">${filters.map(([k,v])=>`<span class="chip brand">${esc(filterLabels[k])} · ${esc(filterValue(k,v))}</span>`).join("")}</div>${sourceNotes()}</div></details></header>
          <button class="fullscreen-exit" data-fullscreen aria-label="Quitter le plein écran">✕ Quitter le plein écran</button>
          <nav class="tabs" role="tablist" aria-label="Parcours Lead Generator">${configuredTabs.map(row=>tab(row.id,row.label,row.count)).join("")}</nav>
          <section class="main"><section id="view" class="view active"></section></section>
          <footer class="footer"><span><strong>${selected.size}</strong> lead${selected.size===1?"":"s"} retenu${selected.size===1?"":"s"}</span><div class="footer-actions"><button class="button" data-global="compare" ${selected.size<2?"disabled":""}>Comparer</button><button class="button primary" data-global="qualify" ${selected.size<1?"disabled":""}>Enrichir la sélection</button></div></footer>`;
        app.querySelectorAll("[data-view]").forEach(b=>b.addEventListener("click",()=>{activeView=b.dataset.view;if(activeView==="contacts")contactCompanyId="";persist();render();}));
        app.querySelector("[data-global='compare']")?.addEventListener("click",compare);
        app.querySelector("[data-global='qualify']")?.addEventListener("click",qualify);
        app.querySelectorAll("[data-fullscreen]").forEach(button=>button.addEventListener("click",toggleFullscreen));
        renderView();
        if(data.management_only) { app.querySelector(".footer")?.remove(); app.querySelector(".metrics")?.remove(); }
        applyVisibility(app);
        setDisplayMode(document.documentElement.dataset.displayMode);
      }
      function setDisplayMode(mode) {
        document.documentElement.dataset.displayMode=mode==="fullscreen"?"fullscreen":"inline";
        app.querySelectorAll('[data-fullscreen]').forEach(button => {
          const label=mode==="fullscreen"?"Quitter le plein écran":"Agrandir la vue en plein écran";
          button.title=label; button.setAttribute("aria-label",label);
        });
        window.leadGeneratorMcpApp.updateDisplayModeControls(app.querySelectorAll('[data-fullscreen]'));
      }
      async function toggleFullscreen() {
        const expanded=document.documentElement.dataset.displayMode==="fullscreen"||Boolean(document.fullscreenElement);
        const target=expanded?"inline":"fullscreen";
        try {
          if(typeof window.openai?.requestDisplayMode==="function") {
            const result=await window.openai.requestDisplayMode({mode:target});
            setDisplayMode(result?.mode||target); return;
          }
          if(window.leadGeneratorMcpApp?.connected) {
            const result=await window.leadGeneratorMcpApp.requestDisplayMode(target);
            setDisplayMode(result.mode); return;
          }
          if(target==="fullscreen"&&document.documentElement.requestFullscreen) await document.documentElement.requestFullscreen();
          else if(target==="inline"&&document.fullscreenElement&&document.exitFullscreen) await document.exitFullscreen();
          else throw new Error("fullscreen unavailable");
          setDisplayMode(target);
        } catch {
          window.leadGeneratorMcpApp.showStatus("L’application n’a pas autorisé le plein écran. La vue reste dans le panneau.");
        }
      }
      function tab(id,label,count) { return `<button class="tab" role="tab" data-view="${id}" aria-selected="${activeView===id}">${label}${count===null?"":`<span class="badge">${count}</span>`}</button>`; }
      function renderView() {
        const target=document.getElementById("view"); if(!target)return;
        if(activeView==="objectives") renderObjectives(target);
        if(activeView==="pipeline") renderPipeline(target);
        if(activeView==="companies") renderCompanies(target);
        if(activeView==="contacts") renderContacts(target);
        if(activeView==="visuals") renderVisuals(target);
        if(activeView==="settings") renderSettings(target);
        if(customTabs().some(tab=>tab.tab_id===activeView)) renderDeclarativeTab(target,customTabs().find(tab=>tab.tab_id===activeView));
        applyVisibility(target);
      }
      function renderDeclarativeTab(target,definition) {
        const panels=definition?.panels||[];
        target.innerHTML=`<div class="section-head"><div><h2>${esc(definition?.label||activeView)}</h2><span class="hint">Vue déclarative alimentée par les observations des plugins.</span></div></div><div class="declarative-grid">${panels.map(renderDeclarativePanel).join("")}</div>`;
      }
      function renderDeclarativePanel(panel) {
        const supported=new Set(["facts-list","metrics","timeline","table","map","image-gallery","score-breakdown","status-list","contact-list","form"]);
        if(!supported.has(panel.component)) return `<section class="declarative-panel" data-panel-id="${esc(panel.panel_id)}"><h3>${esc(panel.title)}</h3><p class="error">Composant incompatible : panneau désactivé.</p></section>`;
        const rows=(data.workspace_view_model?.observations||[]).filter(row=>!panel.observation_kind||row.kind===panel.observation_kind);
        const content=rows.length?rows.map(row=>`<div class="evidence-row ${row.status==="hypothesis"?"hypothesis":row.status==="missing"?"missing":""}"><strong>${esc(row.kind)}</strong> · ${esc(typeof row.value==="string"?row.value:JSON.stringify(row.value))}${row.confidence!=null?` <span class="chip">${Math.round(row.confidence*100)}%</span>`:""}</div>`).join(""):`<div class="empty">${esc(panel.empty_state||"Aucune donnée disponible.")}</div>`;
        return `<section class="declarative-panel" data-panel-id="${esc(panel.panel_id)}"><h3>${esc(panel.title)}</h3><div class="evidence-list">${content}</div></section>`;
      }
      function renderObjectives(target) {
        const rows=objectives();
        target.innerHTML=`<div class="section-head"><div><h2>Agents d'objectif</h2><span class="hint">Chaque agent conserve ses consignes, exemples, contexte, documents et conversations.</span></div><button class="button primary" data-create-objective>Créer un objectif</button></div><div class="objective-grid">${rows.length?rows.map(objectiveCard).join(""):`<div class="empty">Aucun objectif. Créez-en un pour cadrer les recherches et les contacts.</div>`}</div>`;
        target.querySelector("[data-create-objective]")?.addEventListener("click",()=>followUp("Crée un nouvel agent d'objectif Lead Generator. Demande seulement les informations réellement manquantes, puis enregistre l'objectif, ses consignes, exemples, rôles cibles et critères de preuve dans le stockage privé local.",false));
        target.querySelectorAll("[data-activate-objective]").forEach(button=>button.addEventListener("click",()=>activateObjective(button.dataset.activateObjective)));
        target.querySelectorAll("[data-edit-objective]").forEach(button=>button.addEventListener("click",()=>editObjective(button.dataset.editObjective)));
        target.querySelectorAll("[data-attach-objective]").forEach(button=>button.addEventListener("click",()=>attachObjectiveDocument(button.dataset.attachObjective)));
        target.querySelectorAll("[data-delete-objective]").forEach(button=>button.addEventListener("click",()=>deleteObjective(button.dataset.deleteObjective,button)));
      }
      function objectiveCard(objective) {
        const id=objective.objective_id||objective.id, agent=objective.agent||{}, active=id===data.active_objective_id;
        const instructions=agent.instructions||objective.instructions||[], examples=agent.examples||objective.examples||[], documents=agent.documents||objective.documents||[];
        const instructionRows=Array.isArray(instructions)?instructions:[instructions];
        return `<article class="objective-card ${active?"active":""}"><div class="objective-head"><div class="agent-identity"><span class="agent-emoji">${esc(agent.emoji||"🎯")}</span><div><h3>${esc(agent.name||objective.name||objective.objective_name||id)}</h3><p class="meta">${esc(objective.goal_natural||objective.description||objective.offer_name||"Objectif à compléter")}</p></div></div><span class="chip ${active?"brand":""}">${active?"Actif":esc(objective.status||"active")}</span></div>
          <div class="objective-section"><strong>Consignes</strong>${instructionRows.length?`<ul class="objective-list">${instructionRows.slice(0,4).map(item=>`<li>${esc(item)}</li>`).join("")}</ul>`:`<p class="meta">À compléter</p>`}</div>
          <div class="objective-section"><div class="fact-line"><span>Cible</span><strong>${esc(objective.target||"À compléter")}</strong></div><div class="fact-line"><span>Zone</span><strong>${esc(objective.geography||"À compléter")}</strong></div><div class="fact-line"><span>Exemples</span><strong>${examples.length||0}</strong></div><div class="fact-line"><span>Documents</span><strong>${documents.length||objective.attachment_count||0}</strong></div><div class="fact-line"><span>Rôles cibles</span><strong>${(agent.target_roles||objective.target_roles||[]).length||0}</strong></div><div class="fact-line"><span>Planification</span><strong>${esc(scheduleLabels[objective.schedule?.sync_status]||"Non activée")}</strong></div></div>
          <div class="actions"><button class="button ${active?"":"primary"}" data-activate-objective="${esc(id)}">${active?"Parler à l'agent":"Activer"}</button><button class="button" data-edit-objective="${esc(id)}">Modifier</button><button class="button" data-attach-objective="${esc(id)}">Associer un document</button><button class="button danger" data-delete-objective="${esc(id)}">Supprimer</button></div><p class="form-feedback" data-objective-feedback="${esc(id)}" role="status" aria-live="polite"></p></article>`;
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
      function miniCard(lead) { const contact=(lead.contacts||[])[0],workforce=employeeBand(lead);return `<article class="mini-card" data-lead-action="${esc(lead.id)}"><div class="company-identity">${companyLogo(lead)}<h3>${esc(lead.company_name)}</h3></div><p>${esc(contact?`${contact.name} · ${contact.role||"poste à confirmer"}`:(lead.naf_code||lead.activity||"Activité à confirmer"))}</p><div class="filters"><span class="chip">${esc(lead.confidence_score==null?"score —":`${lead.confidence_score}% confiance`)}</span>${workforce?`<span class="chip">${esc(workforce)}</span>`:""}</div></article>`; }
      function companyLogo(lead) {
        const visual=(lead.visuals||[]).find(item=>item.kind==="logo"),url=safeUrl(lead.logo_url)||safeUrl(visual?.image_url);
        return `<span class="company-logo" data-logo-state="${url?"loading":"missing"}"><span class="company-logo-initials" role="img" aria-label="Initiales de ${esc(lead.company_name)} — logo indisponible" title="Logo indisponible">${esc(initials(lead.company_name))}</span>${url?`<img src="${esc(url)}" alt="Logo de ${esc(lead.company_name)}" referrerpolicy="no-referrer" onload="this.parentElement.dataset.logoState='ready'" onerror="this.parentElement.dataset.logoState='error';this.remove()">`:""}</span>`;
      }
      function renderCompanies(target) {
        target.innerHTML=`<div class="section-head"><div><h2>Entreprises</h2><span class="hint">Faits juridiques, signaux et informations manquantes.</span></div><input aria-label="Filtrer les entreprises" type="search" value="${esc(searchText)}" placeholder="Filtrer par nom, NAF, activité…"></div><div class="company-grid">${leads().length?leads().map(companyCard).join(""):`<div class="empty">Aucune entreprise ne correspond au filtre.</div>`}</div>`;
        const input=target.querySelector("input[type='search']"); input?.addEventListener("input",()=>{searchText=input.value;persist();renderView();}); bindLeadButtons(target); bindChecks(target);
        target.querySelectorAll("[data-show-contacts]").forEach(button=>button.addEventListener("click",()=>showCompanyContacts(button.dataset.showContacts)));
      }
      function showCompanyContacts(id="") {
        contactCompanyId=(data.leads||[]).some(lead=>lead.id===id)?id:"";
        activeView="contacts";persist();render();
        const heading=document.getElementById("contacts-heading");heading?.focus();heading?.scrollIntoView({block:"start"});
      }
      function companyCard(lead) {
        const candidate=safeUrl(lead.representative_image_url),logo=safeUrl(lead.logo_url)||safeUrl((lead.visuals||[]).find(item=>item.kind==="logo")?.image_url),image=candidate!==logo?candidate:null, aerial=parkingAerialUrl(lead), website=safeUrl(lead.website_url), legal=safeUrl(lead.legal_profile_url), workforce=employeeBand(lead),focus=lead.aerial_focus||lead.location;
        const aerialView=window.leadGeneratorAerial.render({image:aerial,source:lead.aerial_source_url,small:true,alt:`Vue aérienne centrée sur ${focus?.label||lead.company_name}`,caption:`Vue IGN resserrée sur ${focus?.label||"l’établissement"} · échelle bâtiment / parking`});
        const media=image||aerialView?`<div class="company-media">${image?`<div class="cover"><img src="${esc(image)}" alt="Image représentative de ${esc(lead.company_name)}" referrerpolicy="no-referrer" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'hint',textContent:'Image représentative indisponible'}))"></div>`:""}${aerialView}</div>`:"";
        return `<article class="card company-card${media?"":" no-media"}"><label class="check-wrap"><input class="check" data-select="${esc(lead.id)}" type="checkbox" ${selected.has(lead.id)?"checked":""} aria-label="Sélectionner ${esc(lead.company_name)}"></label>${media}<div class="card-body"><div class="company-identity">${companyLogo(lead)}<div><h3>${esc(lead.company_name)}</h3><p class="meta">${lead.siren?`SIREN ${esc(lead.siren)} · `:""}${esc(lead.naf_code||"NAF à confirmer")}</p></div></div>${lead.company_description?`<p class="company-description">${esc(lead.company_description)}</p>`:""}
          <div class="actions">${tabRows(data.leads||[]).some(tab=>tab.id==="contacts")?`<button class="button primary" data-show-contacts="${esc(lead.id)}" aria-label="Voir les contacts de ${esc(lead.company_name)}">Voir les contacts (${(lead.contacts||[]).length})</button>`:""}</div>
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
        const companies=(data.leads||[]).filter(lead=>!contactCompanyId||lead.id===contactCompanyId);
        target.innerHTML=`<div class="section-head"><div><h2 id="contacts-heading" tabindex="-1">Décideurs et contacts</h2><span class="hint">${contactCompanyId?`Contacts de ${esc(companies[0]?.company_name||"l’entreprise")}. `:"Contacts regroupés par entreprise. "}Email et numéro restent séparés et soumis à confirmation.</span></div>${contactCompanyId?`<button class="button" data-all-contacts>Tous les contacts</button>`:""}</div>${linkedinConnectionPanel()}${companies.length?companies.map(lead=>{
          const people=(lead.contacts||[]).map(contact=>({...contact,lead})).sort((a,b)=>(a.rank||99)-(b.rank||99));
          return `<section class="contact-company" data-contact-company="${esc(lead.id)}"><div class="section-head"><div class="company-identity">${companyLogo(lead)}<div><h3>${esc(lead.company_name)}</h3><p class="meta">${lead.siren?`SIREN ${esc(lead.siren)} · `:""}${people.length} contact(s)${selected.has(lead.id)?" · Entreprise sélectionnée":""}</p></div></div><button class="button" data-find-contact="${esc(lead.id)}">Trouver les décideurs</button></div><div class="contact-grid">${people.length?people.map(contactCard).join(""):`<div class="empty">Aucun contact pour cette entreprise. ${lead.pipeline?.contact_discovery==="in_progress"?"Recherche en cours…":"Lancez la recherche de décideurs."}</div>`}</div></section>`;
        }).join(""):`<div class="empty">Aucune entreprise dans cette vue.</div>`}`;
        target.querySelectorAll("[data-public-enrich]").forEach(b=>b.addEventListener("click",()=>enrichPublicContact(b.dataset.publicEnrich,b.dataset.contact)));
        target.querySelectorAll("[data-add-contact]").forEach(b=>b.addEventListener("click",()=>addContact(b.dataset.addContact,b.dataset.contact)));
        target.querySelectorAll("[data-coordinate]").forEach(b=>b.addEventListener("click",()=>prepareEnrichment(b.dataset.coordinate,b.dataset.contact,b.dataset.field)));
        target.querySelectorAll("[data-find-contact]").forEach(b=>b.addEventListener("click",()=>findContact(b.dataset.findContact)));
        target.querySelector("[data-all-contacts]")?.addEventListener("click",()=>showCompanyContacts());
        target.querySelector("[data-linkedin-session]")?.addEventListener("click",()=>resumeLinkedin(companies));
      }
      function linkedinConnectionPanel() {
        const connection=(data.integrations||[]).find(item=>item.service==="linkedin_review")||{},observed=Date.parse(connection.observed_at||""),fresh=Number.isFinite(observed)&&Date.now()-observed>=0&&Date.now()-observed<15*60*1000;
        const state=connection.status==="disabled"?"disabled":fresh?connection.status:"unknown";
        const labels={connected:"Connexion observée",login_required:"Connexion requise",checkpoint:"Action requise",unavailable:"Navigateur indisponible",disabled:"Désactivé",unknown:"À vérifier"};
        const hints={connected:"Reprenez les profils, photos et publications manquants. La connexion sera revérifiée dans le navigateur.",login_required:"Connectez-vous directement dans le volet Navigateur de cette conversation. Dans Claude, ouvrez le bouton Navigateur si ce volet est masqué.",checkpoint:"Terminez vous-même le contrôle LinkedIn dans le navigateur avant la reprise.",unavailable:"L'accès au navigateur doit être vérifié dans cette application.",disabled:"La recherche LinkedIn connectée est désactivée dans cette configuration.",unknown:"Le compte n'a pas été vérifié récemment pour cette vue. Ouvrez LinkedIn pour vérifier la connexion et reprendre les profils."};
        const label=state==="connected"?"Reprendre sur LinkedIn":state==="login_required"?"Se connecter à LinkedIn":"Ouvrir LinkedIn";
        return `<section class="panel linkedin-connection" aria-label="Connexion LinkedIn"><div class="section-head"><div><h3>LinkedIn · ${esc(labels[state]||labels.unknown)}</h3><p class="hint">${esc(hints[state]||hints.unknown)}</p></div>${state!=="disabled"?`<button class="button primary" data-linkedin-session>${label}</button>`:""}</div></section>`;
      }
      function resumeLinkedin(rows) {
        const scope=data.browser_scope_id?` Réutilise le périmètre navigateur ${data.browser_scope_id}.`:"";
        return followUp(`Reprends uniquement la recherche LinkedIn des contacts de : ${context(rows)}.${scope} Charge le workflow lead-linkedin-browser et utilise réellement le navigateur de cette application. Réutilise l'onglet LinkedIn et vérifie l'état visible. Si une connexion ou un contrôle est demandé, montre le volet navigateur, demande-moi immédiatement de terminer cette étape dans l'onglet et attends ma réponse. Ne lis aucun identifiant, cookie ou message privé. Une fois connecté, recherche les profils, photos et publications manquants des contacts pertinents, au maximum cinq par entreprise, sans refaire l'enrichissement des sites officiels. Réaffiche les contacts en conservant les fiches, les preuves et browser_scope_id. Aucun appel payant, aucun envoi, aucune écriture CRM.`);
      }
      function contactCard({lead,...contact}) {
        const photo=safeUrl(contact.profile_image_url), linkedin=safeUrl(contact.linkedin_url), source=safeUrl(contact.source_url), publicDone=contact.public_profile_status==="complete", added=Boolean(contact.added_to_contacts||contact.contact_id);
        const evidenceUrls=[...new Set([source,...(contact.evidence_urls||[]).map(safeUrl)].filter(Boolean))];
        return `<article class="card contact-card"><div class="card-body"><div class="contact-top"><div class="avatar">${esc(initials(contact.name))}${photo?`<img src="${esc(photo)}" alt="Photo de ${esc(contact.name)}" referrerpolicy="no-referrer" onerror="this.remove()">`:""}</div><div><h3>${contact.rank?`${contact.rank}. `:""}${esc(contact.name)}</h3><p class="meta">${esc(contact.role||"Poste à confirmer")}</p><span class="chip ${contact.identity_status==="verified"?"brand":contact.identity_status==="ambiguous"?"warn":""}">${esc(({verified:"Identité vérifiée",unverified:"Identité à vérifier",ambiguous:"Identité ambiguë",stale:"Identité à actualiser"})[contact.identity_status]||"Identité à vérifier")}</span> <span class="chip ${publicDone?"brand":contact.public_profile_status==="partial"?"warn":""}">${esc(({complete:"Profil complété",partial:"Profil partiel",in_progress:"Recherche en cours",unavailable:"Profil indisponible",not_requested:"Profil à rechercher"})[contact.public_profile_status]||"Profil à rechercher")}</span></div></div>
          <details class="evidence contact-details"${data.ui?.theme?.density==="compact"?"":" open"}><summary>Détails, coordonnées et preuves</summary>${contact.description?`<p>${esc(contact.description)}</p>`:""}<div class="contact-data"><div class="contact-value"><span class="status-dot ${contact.work_email?"ok":""}"></span>${esc(contact.work_email||"Email professionnel non recherché")}</div><div class="contact-value"><span class="status-dot ${contact.phone?"ok":""}"></span>${esc(contact.phone||"Téléphone non recherché")}</div></div><p class="meta">${esc(contact.evidence)}</p>${contact.selection_reason?`<div class="evidence-row signal"><strong>Pourquoi ce contact</strong> · ${esc(contact.selection_reason)}${contact.confidence_score!=null?` · ${esc(contact.confidence_score)}%`:""}</div>`:""}<div class="actions">${evidenceUrls.slice(0,2).map((url,index)=>`<a class="button" href="${esc(url)}" target="_blank" rel="noopener noreferrer">Preuve ${index+1} ↗</a>`).join("")}${safeUrl(contact.profile_image_source_url)?`<a class="button" href="${esc(safeUrl(contact.profile_image_source_url))}" target="_blank" rel="noopener noreferrer">Source photo${contact.profile_image_access_mode==="authenticated_browser"?" · connecté":""} ↗</a>`:""}</div></details>
          ${(contact.recent_posts||[]).length?`<details class="evidence"><summary>Publications observées (${contact.recent_posts.length})</summary><div class="evidence-list">${contact.recent_posts.map(post=>`<div class="evidence-row">${esc(post.summary)} <span class="meta">${esc(post.published_at||"Date de publication inconnue")} · ${esc(post.observed_at||"Date d’observation manquante")} · ${post.access_mode==="authenticated_browser"?"Navigateur connecté":"Source publique"}</span> ${sourceLink(post)}</div>`).join("")}</div></details>`:""}
          <div class="actions">${linkedin?`<a class="button" href="${esc(linkedin)}" target="_blank" rel="noopener noreferrer">LinkedIn ↗</a>`:""}${!publicDone?`<button class="button" data-public-enrich="${esc(lead.id)}" data-contact="${esc(contact.name)}">Enrichir le profil</button>`:""}${!added?`<button class="button" data-add-contact="${esc(lead.id)}" data-contact="${esc(contact.name)}">Ajouter comme contact</button>`:""}${publicDone&&added&&contact.identity_status==="verified"?`<button class="button primary" data-coordinate="${esc(lead.id)}" data-contact="${esc(contact.name)}" data-field="email">Trouver l’email</button><button class="button primary" data-coordinate="${esc(lead.id)}" data-contact="${esc(contact.name)}" data-field="phone">Trouver le numéro</button>`:""}</div></div></article>`;
      }
      function renderVisuals(target) {
        const rows=visuals(); target.innerHTML=`<div class="section-head"><div><h2>Identité visuelle</h2><span class="hint">Candidats issus des sites officiels, à valider avant réutilisation.</span></div>${selected.size?`<button class="button primary" data-discover-visuals>Rechercher pour la sélection</button>`:""}</div><div class="gallery">${rows.length?rows.map(visualCard).join(""):`<div class="empty">Aucun visuel officiel relevé.</div>`}</div>`;
        target.querySelector("[data-discover-visuals]")?.addEventListener("click",discoverVisuals);
      }
      function visualCard({lead,...visual}) { const image=safeUrl(visual.image_url), source=safeUrl(visual.source_url),labels={logo:"Logo",representative_image:"Image représentative",aerial_image:"Vue du ciel"};return `<article class="visual"><div class="visual-frame">${image?`<img referrerpolicy="no-referrer" src="${esc(image)}" alt="Visuel candidat de ${esc(lead.company_name)}" onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'visual-fallback',textContent:'Image non chargée — ouvrez l’image ou sa source.'}))">`:`<div class="visual-fallback">Aperçu indisponible</div>`}</div><div class="visual-info"><span class="chip">${labels[visual.kind]||"Visuel"}</span> <span class="chip">${esc(visual.confidence)}</span><h3>${esc(lead.company_name)}</h3><p class="meta">${esc(visual.evidence)}</p>${image?`<a class="button" href="${esc(image)}" target="_blank" rel="noopener noreferrer">Ouvrir l’image ↗</a>`:""} ${source?`<a class="button" href="${esc(source)}" target="_blank" rel="noopener noreferrer">Voir la source ↗</a>`:""}</div></article>`; }
      function renderHubspot(target) {
        const integrations=data.integrations||[], hub=data.hubspot||{}, chosen=selectedLeads(), ready=chosen.filter(x=>(x.contacts||[]).some(c=>c.work_email));
        target.innerHTML=`<div class="section-head"><div><h2>Connexions et remise au CRM</h2><span class="hint">Aucun crédit ni écriture n'est déclenché depuis cette vue.</span></div></div><div class="integrations">${integrations.length?integrations.map(integrationCard).join(""):`<div class="empty">Lancez le diagnostic des connexions.</div>`}</div>
          <div class="crm-layout"><section class="panel"><h3>Contacts prêts</h3><div class="preview-list">${chosen.length?chosen.map(lead=>{const c=(lead.contacts||[]).find(x=>x.work_email);return `<div class="preview-row"><span><strong>${esc(lead.company_name)}</strong><br><span class="meta">${esc(c?`${c.name} · ${c.work_email}`:"Email professionnel manquant")}</span></span><span class="chip ${c?"brand":"warn"}">${c?"Prêt":"Bloqué"}</span></div>`;}).join(""):`<div class="empty">Sélectionnez des leads à remettre au CRM.</div>`}</div></section>
          <section class="panel"><h3>Préparer HubSpot</h3><label for="list-name">Nom de la liste</label><input id="list-name" type="text" value="${esc(hub.list_name||"")}" placeholder="Prospects · campagne"><label for="owner-name">Collègue à qui attribuer</label><input id="owner-name" type="text" value="${esc(hub.owner_email||hub.owner_name||"")}" placeholder="email exact ou nom complet"><div class="fact-line"><span>Leads sélectionnés</span><strong>${chosen.length}</strong></div><div class="fact-line"><span>Contacts avec email</span><strong>${ready.length}</strong></div><div class="fact-line"><span>Sociétés prévues</span><strong>${(hub.planned_companies||[]).length}</strong></div><div class="fact-line"><span>Associations contact ↔ société</span><strong>${(hub.planned_associations||[]).length}</strong></div><div class="actions"><button class="button" data-diagnose>Vérifier les connexions</button><button class="button primary" data-prepare-crm ${ready.length<1?"disabled":""}>Demander la confirmation</button></div><p class="meta">L'écriture HubSpot restera bloquée jusqu'à votre confirmation explicite dans le chat. La vérification relira les propriétés, le propriétaire, l'association société et l'appartenance à la liste.</p></section></div>`;
        target.querySelectorAll("[data-setup]").forEach(b=>b.addEventListener("click",()=>setupIntegration(b.dataset.setup)));
        target.querySelector("[data-diagnose]")?.addEventListener("click",diagnose);
        target.querySelector("[data-prepare-crm]")?.addEventListener("click",()=>prepareCrm(ready));
      }
      function renderSettings(target) {
        const configured=Number(data.preferences?.desired_lead_count??10),value=Number.isInteger(configured)&&configured>=1&&configured<=25?configured:10;
        target.innerHTML=`<div class="section-head"><div><h2>Réglages</h2><span class="hint">Préférences de recherche, connexions et préparation CRM.</span></div></div><div class="settings-layout"><section class="panel settings-preferences"><h3>Volume de recherche</h3><form data-search-settings><label for="desired-lead-count">Nombre de leads souhaité</label><input id="desired-lead-count" name="desired_lead_count" type="number" inputmode="numeric" min="1" max="25" step="1" value="${value}" required aria-describedby="desired-lead-count-help settings-feedback"><p id="desired-lead-count-help" class="hint">Entre 1 et 25 leads, limite maximale d’une page du registre public.</p><div class="actions"><button class="button primary" type="submit">Enregistrer</button></div><p id="settings-feedback" class="form-feedback" role="status" aria-live="polite"></p></form></section><section data-settings-hubspot aria-label="HubSpot"></section></div>`;
        renderHubspot(target.querySelector("[data-settings-hubspot]"));
        if(data.management_only||data.initial_view==="objectives"){
          const schedulePanel=document.createElement("section");schedulePanel.className="panel";schedulePanel.setAttribute("aria-label","Planification par objectif");
          target.querySelector(".settings-layout").prepend(schedulePanel);renderScheduleSettings(schedulePanel);
        }
        target.querySelector("[data-search-settings]")?.addEventListener("submit",event=>{
          event.preventDefault();
          const input=target.querySelector("#desired-lead-count"),feedback=target.querySelector("#settings-feedback"),desired=Number(input?.value);
          if(!Number.isInteger(desired)||desired<1||desired>25){feedback.textContent="Saisissez un nombre entier entre 1 et 25.";feedback.classList.add("error");input?.focus();return;}
          feedback.textContent="Enregistrement demandé…";feedback.classList.remove("error");
          followUp(`Définis le nombre de leads souhaité à ${desired} avec l'outil set_lead_search_preferences, puis réaffiche la page Réglages pour confirmer la valeur. Ne lance aucune recherche.`,false);
        });
      }
      function integrationCard(item) { const names={linkedin_public:"LinkedIn public",linkedin_review:"LinkedIn · mon compte",enrow:"Enrow",fullenrich:"FullEnrich",hubspot:"HubSpot"};const labels={available:"Disponible",not_configured:"Non connecté",configured:"Configuré",connected:"Connecté",invalid:"Clé invalide",disabled:"Désactivé",unknown:"À vérifier",login_required:"Connexion requise",checkpoint:"Action requise",unavailable:"Indisponible"};const setupAllowed=!['available','connected','disabled','linkedin_public'].includes(item.status)&&item.service!=="linkedin_public";return `<article class="integration"><div class="integration-head"><h3>${names[item.service]||esc(item.service)}</h3><span class="status ${esc(item.status)}">${labels[item.status]||esc(item.status)}</span></div><p class="meta">${esc(item.purpose)}</p><p class="hint">${esc(item.recommendation)}</p>${setupAllowed?`<button class="button" data-setup="${esc(item.service)}">${item.service==="linkedin_review"?"Ouvrir LinkedIn":"Configurer"}</button>`:""}</article>`; }
      function sourceNotes() { const rows=data.search?.limitations||[];return rows.length?`<details class="source-notes"><summary>Limites des données (${rows.length})</summary><ul>${rows.map(x=>`<li>${esc(x)}</li>`).join("")}</ul></details>`:""; }
      function bindChecks(target) { target.querySelectorAll("[data-select]").forEach(input=>input.addEventListener("change",()=>{input.checked?selected.add(input.dataset.select):selected.delete(input.dataset.select);persist();render();})); }
      function bindLeadButtons(target) { target.querySelectorAll("[data-lead-action]").forEach(el=>el.addEventListener("click",()=>openLead(el.dataset.leadAction))); }
      function context(rows=selectedLeads()) { return rows.map(x=>`${x.company_name}${x.siren?` (SIREN ${x.siren})`:""}`).join(", "); }
      function scopedPrompt(prompt) { const objective=activeObjective(),id=objective?.objective_id||objective?.id;return id?`Objectif Lead Generator explicite : ${objective.name||objective.objective_name||id} (${id}). Conserve ce périmètre et refuse tout objective_id contradictoire.\n\n${prompt}`:prompt; }
      async function followUp(prompt,applyScope=true) { const scoped=applyScope?scopedPrompt(prompt):prompt;if(typeof window.openai?.sendFollowUpMessage==="function") return window.openai.sendFollowUpMessage({prompt:scoped,scrollToBottom:true});return window.leadGeneratorMcpApp.sendMessage(scoped); }
      function activateObjective(id) { followUp(`Active l'agent d'objectif ${id} pour cette conversation, charge son contexte complet et ses documents, puis affiche l'onglet Objectifs mis à jour.`,false); }
      __OBJECTIVE_MANAGEMENT_JS__
      function publicEnrichmentPrompt(rows) { return `Lance maintenant le parcours d'enrichissement public complet pour : ${context(rows)}. Pour chaque entreprise, conserve l'objectif actif et l'identité légale exacte. Recherche puis affiche le site officiel, la description, le logo, une image représentative distincte, la vue aérienne IGN centrée sur l'établissement ou le parking si ses coordonnées sont publiquement vérifiées, le dirigeant actuel avec preuves indépendantes, sa photo publique vérifiable, sa description, ses actualités et ses derniers posts publiquement accessibles, les actualités récentes condensées selon l'objectif et un premier angle de prospection sourcé. Examine les profils professionnels via les sources publiques et mon compte LinkedIn dans le navigateur disponible dans cette application, sans contournement. Exécute réellement le handoff navigateur : réutilise la session ou ouvre LinkedIn et laisse-moi me connecter si nécessaire ; s'il est indisponible, indique cette limite. Indique la couverture réelle, classe les cinq meilleurs contacts selon l'objectif et rends chacun enrichissable puis ajoutable. Termine par render_lead_workspace avec initial_view=companies, sans afficher le gestionnaire d'objectifs. Ne cherche ni email ni téléphone : ces deux coordonnées restent des actions séparées sous confirmation. Ne contacte personne.`; }
      function openLead(id) { const lead=(data.leads||[]).find(x=>x.id===id);if(lead)followUp(publicEnrichmentPrompt([lead])); }
      function qualify() { if(selected.size)followUp(publicEnrichmentPrompt(selectedLeads())); }
      function compare() { if(selected.size>1)followUp(`Compare uniquement ces leads : ${context()}. Montre les preuves, signaux, contacts et informations manquantes dans l'espace visuel Lead Generator. Ne contacte personne.`); }
      function findContact(which) { const rows=which==="selection"?selectedLeads():(data.leads||[]).filter(x=>x.id===which);followUp(`Trouve le bon décideur public pour : ${context(rows)}. Exige une preuve reliant nom, poste actuel et entreprise. Ajoute LinkedIn et photo publique seulement sans ambiguïté, puis actualise l'onglet Contacts.`); }
      function enrichPublicContact(id,name) { const lead=(data.leads||[]).find(x=>x.id===id);followUp(`Enrichis uniquement le profil public de ${name} chez ${lead?.company_name||"l'entreprise"}. Vérifie nom, poste et entreprise sur des sources indépendantes, puis relève photo publique vérifiable, description, actualités et derniers posts visibles via les sources publiques ou mon compte LinkedIn dans le navigateur disponible dans cette application, sans contournement. Ne cherche ni email ni téléphone.`); }
      function addContact(id,name) { const lead=(data.leads||[]).find(x=>x.id===id);followUp(`Ajoute ${name} comme contact retenu de ${lead?.company_name||"l'entreprise"} dans la fiche Lead Generator, sans écriture CRM et sans recherche payante. Conserve les preuves, marque added_to_contacts=true et réaffiche l'onglet Contacts.`); }
      function prepareEnrichment(id,name,field) { const lead=(data.leads||[]).find(x=>x.id===id),label=field==="phone"?"numéro professionnel":"email professionnel";followUp(`Prépare la recherche du ${label} de ${name} chez ${lead?.company_name||"l'entreprise"}. Affiche d'abord l'identité, les connexions, le champ exact et la cascade Enrow puis FullEnrich. Ne lance aucun appel payant avant ma confirmation explicite.`); }
      function discoverVisuals() { followUp(`Recherche les logos et images représentatives sur les sites officiels de : ${context()}. Garde l'URL source, le niveau de confiance et actualise l'onglet Visuels.`); }
      function setupIntegration(service) { if(service==="linkedin_review")return followUp("Utilise mon compte LinkedIn dans le navigateur disponible dans cette application pour la recherche professionnelle. Réutilise l’onglet existant ou ouvre LinkedIn ; si une connexion est nécessaire, laisse-moi la faire dans cet onglet puis reprends la recherche. Aucun export de cookies et aucun identifiant dans le chat.");followUp(`Aide-moi à configurer ${service} pour Lead Generator. Explique son utilité et la variable d'environnement attendue, sans me demander de coller un secret dans le chat.`); }
      function diagnose() { followUp("Vérifie les connexions Enrow, FullEnrich et HubSpot sans consommer de crédit, puis actualise l'espace visuel Lead Generator."); }
      function prepareCrm(rows) { const list=document.getElementById("list-name")?.value.trim(),owner=document.getElementById("owner-name")?.value.trim();followUp(`Prépare sans l'exécuter la synchronisation HubSpot de : ${context(rows)}. Liste : ${list||"à définir"}. Propriétaire : ${owner||"non attribué"}. Affiche le récapitulatif exact et demande ma confirmation explicite avant toute écriture CRM.`); }
      document.addEventListener("fullscreenchange",()=>setDisplayMode(document.fullscreenElement?"fullscreen":"inline"));
      document.addEventListener("keydown",event=>{
        if(event.key==="Escape"&&document.documentElement.dataset.displayMode==="fullscreen"&&!document.fullscreenElement) toggleFullscreen();
      });
      window.addEventListener("openai:set_globals",event=>{const globals=event.detail?.globals||{};applyGlobals(globals);const incoming=globals.toolOutput||globals.toolResponse;if(incoming)hydrate(incoming);});
      window.addEventListener("leadgenerator:host-context",event=>applyGlobals(event.detail||{}));
      window.addEventListener("leadgenerator:tool-result",event=>hydrate(event.detail));
      applyGlobals(window.openai||{});applyGlobals(window.leadGeneratorMcpApp?.hostContext||{});hydrate(window.openai?.toolOutput||window.leadGeneratorMcpApp?.toolResult||window.openai);
      window.addEventListener("leadgenerator:tool-error",()=>{if(!data)app.textContent="La fiche n’a pas pu être affichée : l’outil a signalé une erreur. Claude doit corriger cet appel, sans relancer toute la recherche.";else window.leadGeneratorMcpApp.showStatus("La mise à jour a échoué. La dernière fiche valide reste affichée.");});
      setTimeout(()=>{const message=document.getElementById("loading-message");if(!data&&message)message.textContent="Préparation des cartes et des filtres…";},1200);
      setTimeout(()=>{const message=document.getElementById("loading-message");if(!data&&message)message.textContent="Le chargement continue…";},5000);
      setTimeout(()=>{const message=document.getElementById("loading-message");if(!data&&message&&!window.leadGeneratorMcpApp.toolError)message.textContent="Le panneau attend encore les données. La vue s’affichera dès leur réception.";},15000);
    })();
  </script>
</body>
</html>"""

LEAD_WORKSPACE_HTML = LEAD_WORKSPACE_HTML.replace(
    "</head>",
    f"<style>{AERIAL_VIEW_CSS}</style><script>{MCP_APP_BRIDGE_JS}\n{AERIAL_VIEW_JS}</script>\n</head>",
    1,
).replace("__OBJECTIVE_MANAGEMENT_JS__", OBJECTIVE_MANAGEMENT_JS, 1)
