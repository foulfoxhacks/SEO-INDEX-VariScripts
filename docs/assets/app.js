'use strict';

const tools = [
  {id:'score',name:'Index Readiness Score',cat:['seo','geo','aeo'],icon:'◉',desc:'Category scorecards for Google, Bing, general search, GEO, and AEO with evidence coverage and assurance.',tag:'seo-index score'},
  {id:'links',name:'Internal Link Graph',cat:['seo'],icon:'⌬',desc:'Crawl one host into a relationship graph with depth, orphan, redirect, dead-end, noindex, and canonical findings.',tag:'seo-index links'},
  {id:'serve',name:'Local Live Workbench',cat:['seo','geo','aeo','indexing'],icon:'◫',desc:'Serve this dashboard from localhost with a token-protected live audit API. No cloud proxy required.',tag:'seo-index serve'},
  {id:'redirect',name:'Redirect Lab',cat:['seo'],icon:'↪',desc:'Trace every hop, loop, status, host change, HTTPS downgrade, temporary redirect, and final destination.',tag:'seo-index redirect'},
  {id:'robots',name:'Crawler Access Matrix',cat:['seo','geo'],icon:'🤖',desc:'Compare Googlebot, bingbot, OAI-SearchBot, ClaudeBot, PerplexityBot, GPTBot, and custom agents.',tag:'seo-index robots'},
  {id:'hreflang',name:'Hreflang Auditor',cat:['seo'],icon:'🌐',desc:'Validate language tags, duplicate declarations, self references, alternate status, and reciprocal links.',tag:'seo-index hreflang'},
  {id:'schema',name:'Structured Data Graph',cat:['seo','geo','aeo'],icon:'⌘',desc:'Inspect JSON-LD syntax, Schema.org types, sameAs identity links, duplicate @id values, and context usage.',tag:'seo-index schema'},
  {id:'geo',name:'GEO Entity Audit',cat:['geo'],icon:'✦',desc:'Check AI crawler access, entity identity, source support, freshness, machine readability, and llms.txt.',tag:'seo-index geo'},
  {id:'aeo',name:'AEO Answer Audit',cat:['aeo'],icon:'?',desc:'Inspect question headings, concise answer blocks, lists, tables, answer schema, authorship, and freshness.',tag:'seo-index aeo'},
  {id:'canonical',name:'Canonical Guard',cat:['seo'],icon:'◇',desc:'Audit sitemap URLs for final-URL, host, redirect, and rel=canonical disagreement.',tag:'seo-index canonical'},
  {id:'sitemap',name:'Sitemap Doctor',cat:['seo','indexing'],icon:'☷',desc:'Validate XML, GZip, sitemap indexes, duplicates, lastmod, mixed hosts, status codes, and redirects.',tag:'seo-index sitemap'},
  {id:'indexnow',name:'IndexNow Runner',cat:['indexing'],icon:'⚡',desc:'Validate hosted keys, canonical hosts, recursive sitemaps, deduplicate URLs, batch, dry-run, and submit.',tag:'seo-index indexnow'}
];

const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];
const escapeHtml = (value='') => String(value).replace(/[&<>"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[char]));

function renderTools(filter='all') {
  const list = filter === 'all' ? tools : tools.filter(tool => tool.cat.includes(filter));
  $('#tool-grid').innerHTML = list.map(tool => `
    <article class="tool-card">
      <span class="icon">${tool.icon}</span>
      <h3>${escapeHtml(tool.name)}</h3>
      <p>${escapeHtml(tool.desc)}</p>
      <span class="tag">${escapeHtml(tool.tag)}</span>
    </article>`).join('');
}
$$('[data-filter]').forEach(button => button.addEventListener('click', () => {
  $$('[data-filter]').forEach(item => item.classList.remove('active'));
  button.classList.add('active');
  renderTools(button.dataset.filter);
}));
renderTools();

const toolSelect = $('#tool-select');
toolSelect.innerHTML = tools.map(tool => `<option value="${tool.id}">${escapeHtml(tool.name)}</option>`).join('');
function quoteArg(value) {
  return /[\s&|<>]/.test(value) ? `'${value.replaceAll("'", "''")}'` : value;
}
function buildCommand() {
  const platform = $('#platform').value;
  const tool = toolSelect.value;
  const url = $('#target-url').value.trim();
  const sitemap = $('#sitemap-url').value.trim();
  const key = $('#key-url').value.trim();
  const profile = $('#profile').value;
  const jsonPath = $('#json-path').value.trim();
  const args = [];
  if (tool === 'score') {
    if (url) args.push('--url', url);
    args.push('--engine', profile);
    if (sitemap) args.push('--sitemap', sitemap);
    if (key) args.push('--key-location', key);
  } else if (tool === 'links') {
    if (url) args.push('--url', url);
    if (sitemap) args.push('--sitemap', sitemap);
    args.push('--max-pages', '250', '--max-depth', '6');
    if (jsonPath) args.push('--json', jsonPath);
    args.push('--html', './reports/internal-links.html');
  } else if (tool === 'serve') {
    args.push('--port', '8765');
  } else if (['redirect','robots','hreflang','schema','geo','aeo'].includes(tool)) {
    if (url) args.push('--url', url);
    if (tool === 'hreflang') args.push('--check-alternates');
  } else if (['canonical','sitemap'].includes(tool)) {
    if (sitemap || url) args.push('--sitemap', sitemap || url);
    if (tool === 'sitemap') args.push('--check-pages', '100');
  } else if (tool === 'indexnow') {
    if (sitemap || url) args.push('--sitemap', sitemap || url);
    if (key) args.push('--key-location', key);
    args.push('--dry-run');
  }
  if (jsonPath && !['indexnow','links','serve'].includes(tool)) args.push('--json', jsonPath);
  const joiner = platform === 'powershell' ? ' `\n  ' : ' \\\n  ';
  return `seo-index ${tool}${args.length ? joiner + args.map(quoteArg).join(joiner) : ''}`;
}
function updateCommand() {
  $('#command-preview code').textContent = buildCommand();
  const tool = toolSelect.value;
  const notes = {
    indexnow: 'Starts in dry-run mode. Remove <code>--dry-run</code> only after validation succeeds.',
    links: 'Creates JSON evidence plus a standalone interactive HTML site graph.',
    serve: 'Starts a token-protected localhost server and opens the live graphical workbench.'
  };
  $('#command-notes').innerHTML = notes[tool] || 'Use <code>--json</code> to load the result into the report viewer.';
}
$('#command-form').addEventListener('input', updateCommand);
$('#copy-command').addEventListener('click', async () => {
  await navigator.clipboard.writeText(buildCommand());
  $('#copy-command').textContent = 'Copied';
  setTimeout(() => $('#copy-command').textContent = 'Copy', 1200);
});
updateCommand();

let matrix;
fetch('matrix.json').then(response => response.json()).then(data => {
  matrix = data;
  const select = $('#matrix-profile');
  select.innerHTML = Object.entries(data.profiles).map(([key, profile]) => `<option value="${key}">${escapeHtml(profile.label)}</option>`).join('');
  select.addEventListener('change', renderMatrix);
  renderMatrix();
}).catch(error => {
  $('#matrix-categories').innerHTML = `<p class="status fail">Could not load matrix.json: ${escapeHtml(error.message)}</p>`;
});
function renderMatrix() {
  if (!matrix) return;
  const key = $('#matrix-profile').value || Object.keys(matrix.profiles)[0];
  const profile = matrix.profiles[key];
  const categories = Object.entries(profile.categories);
  $('#matrix-summary').innerHTML = `
    <div class="summary-card"><strong>${escapeHtml(profile.profileType)}</strong><span>Profile type</span></div>
    <div class="summary-card"><strong>${categories.length}</strong><span>Weighted categories</span></div>
    <div class="summary-card"><strong>${Object.values(profile.categories).reduce((total, category) => total + Object.keys(category.factors).length, 0)}</strong><span>Factor placements</span></div>`;
  $('#matrix-categories').innerHTML = categories.map(([id, category]) => `
    <article class="category-card">
      <div class="category-head"><div><strong>${escapeHtml(category.label)}</strong><small>${escapeHtml(id)}</small></div><span>${category.weight}%</span></div>
      ${Object.entries(category.factors).map(([factor, weight]) => `<div class="factor-row"><span>${escapeHtml(factor.replaceAll('_',' '))}</span><i style="--w:${weight}%"></i><b>${weight}%</b></div>`).join('')}
    </article>`).join('');
}

function scoreColor(value) {
  return value >= 90 ? '#70f5a4' : value >= 75 ? '#65e6ff' : value >= 60 ? '#ffd76a' : '#ff7188';
}
function renderLinkSummary(data, target) {
  const summary = data.summary || {};
  target.innerHTML = `
    <div class="live-summary-grid">
      <article><strong>${summary.pagesCrawled ?? 0}</strong><span>pages</span></article>
      <article><strong>${summary.internalEdges ?? 0}</strong><span>internal edges</span></article>
      <article><strong>${summary.brokenPages ?? 0}</strong><span>broken pages</span></article>
      <article><strong>${summary.orphanCandidates ?? 0}</strong><span>orphan candidates</span></article>
    </div>`;
}
function renderReport(data) {
  const view = $('#report-view');
  view.classList.remove('report-empty');
  if (data.scores) {
    view.innerHTML = data.scores.map(score => `
      <section class="report-score"><div class="report-header"><div class="score-ring" style="--score:${score.assured_score ?? score.normalized_score};--green:${scoreColor(score.assured_score ?? score.normalized_score)}"><strong>${score.assured_score ?? score.normalized_score}</strong></div><div><h3>${escapeHtml(score.label)}</h3><div class="report-meta">verified ${score.verified_score ?? score.normalized_score}/100 · coverage ${score.coverage}% · ${escapeHtml(score.grade)}</div></div></div>${score.categories ? `<div class="score-summary">${Object.values(score.categories).map(category => `<div class="summary-card"><strong>${category.assuredScore}</strong><span>${escapeHtml(category.label)} · ${category.coverage}% coverage</span></div>`).join('')}</div>` : ''}</section>`).join('');
    return;
  }
  if (data.tool === 'internal-link-graph' || data.schemaVersion === '3.0' && data.edges && data.pages) {
    renderLinkSummary(data, view);
    view.innerHTML += `<pre>${escapeHtml(JSON.stringify(data.findings, null, 2))}</pre>`;
    return;
  }
  if (data.report?.hops) {
    renderRedirect(data, view);
    return;
  }
  view.innerHTML = `<pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre>`;
}
$('#report-file').addEventListener('change', event => {
  const file = event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try { renderReport(JSON.parse(reader.result)); }
    catch (error) { $('#report-view').innerHTML = `<p class="status fail">Invalid JSON: ${escapeHtml(error.message)}</p>`; }
  };
  reader.readAsText(file);
});
const drop = $('#report-drop');
['dragenter','dragover'].forEach(name => drop.addEventListener(name, event => { event.preventDefault(); drop.style.borderColor = 'var(--purple)'; }));
['dragleave','drop'].forEach(name => drop.addEventListener(name, event => { event.preventDefault(); drop.style.borderColor = ''; }));
drop.addEventListener('drop', event => {
  const file = event.dataTransfer.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => { try { renderReport(JSON.parse(reader.result)); } catch (error) { renderReport({error:error.message}); } };
  reader.readAsText(file);
});

$$('[data-tab]').forEach(button => button.addEventListener('click', () => {
  $$('[data-tab]').forEach(item => item.classList.remove('active'));
  $$('.lab-panel').forEach(item => item.classList.remove('active'));
  button.classList.add('active');
  $('#' + button.dataset.tab).classList.add('active');
}));
function result(status, label, message) {
  return `<div class="result-row"><span class="status ${status}">${status.toUpperCase()}</span><div><strong>${escapeHtml(label)}</strong><br><small>${escapeHtml(message)}</small></div></div>`;
}
$('#analyze-html').addEventListener('click', event => {
  event.preventDefault();
  const source = $('#lab-html').value;
  const headers = $('#lab-headers').value;
  const doc = new DOMParser().parseFromString(source, 'text/html');
  const rows = [];
  const status = (headers.match(/HTTP\/\S+\s+(\d+)/i) || [])[1];
  const xrobots = (headers.match(/^x-robots-tag:\s*(.+)$/im) || [])[1] || '';
  const contentType = (headers.match(/^content-type:\s*(.+)$/im) || [])[1] || '';
  rows.push(result(status === '200' ? 'pass' : status ? 'fail' : 'warn', 'HTTP status', status || 'Not provided'));
  rows.push(result(/text\/html|application\/xhtml/i.test(contentType) ? 'pass' : 'warn', 'Content type', contentType || 'Not provided'));
  rows.push(result(/noindex/i.test(xrobots) ? 'fail' : 'pass', 'X-Robots-Tag', xrobots || 'No noindex header detected'));
  const title = doc.querySelector('title')?.textContent.trim() || '';
  const description = doc.querySelector('meta[name="description"]')?.content || '';
  const canonical = doc.querySelector('link[rel~="canonical"]')?.href || '';
  const lang = doc.documentElement.lang;
  const h1 = doc.querySelectorAll('h1').length;
  const jsonld = [...doc.querySelectorAll('script[type="application/ld+json"]')];
  rows.push(result(title ? 'pass' : 'fail', 'Title', title || 'Missing'));
  rows.push(result(description ? 'pass' : 'warn', 'Meta description', description || 'Missing'));
  rows.push(result(canonical ? 'pass' : 'warn', 'Canonical', canonical || 'Missing'));
  rows.push(result(lang ? 'pass' : 'warn', 'Document language', lang || 'Missing html lang'));
  rows.push(result(h1 === 1 ? 'pass' : h1 ? 'warn' : 'fail', 'H1 count', String(h1)));
  let valid = 0; const types = [];
  jsonld.forEach(block => { try { const item = JSON.parse(block.textContent); valid++; JSON.stringify(item, (key, value) => { if (key === '@type') types.push(...(Array.isArray(value) ? value : [value])); return value; }); } catch {} });
  rows.push(result(jsonld.length && valid === jsonld.length ? 'pass' : jsonld.length ? 'fail' : 'warn', 'JSON-LD', `${valid}/${jsonld.length} valid; types: ${[...new Set(types)].join(', ') || 'none'}`));
  const questions = [...doc.querySelectorAll('h1,h2,h3,h4')].filter(item => /\?$|^(who|what|when|where|why|how|can|is|are)\b/i.test(item.textContent.trim())).length;
  rows.push(result(questions ? 'pass' : 'warn', 'Question headings', String(questions)));
  $('#html-results').innerHTML = rows.join('');
});
function robotsGroups(text) {
  const groups = []; let current = {agents:[], rules:[]};
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.replace(/#.*/, '').trim();
    if (!line) continue;
    const [field, ...rest] = line.split(':');
    const value = rest.join(':').trim();
    if (/^user-agent$/i.test(field)) {
      if (current.rules.length) { groups.push(current); current = {agents:[], rules:[]}; }
      current.agents.push(value.toLowerCase());
    } else if (/^(allow|disallow)$/i.test(field)) current.rules.push({type:field.toLowerCase(), path:value});
  }
  if (current.agents.length || current.rules.length) groups.push(current);
  return groups;
}
$('#analyze-robots').addEventListener('click', event => {
  event.preventDefault();
  const text = $('#robots-text').value;
  const agent = $('#robots-agent').value.toLowerCase();
  const path = $('#robots-path').value || '/';
  const groups = robotsGroups(text);
  const applicable = groups.filter(group => group.agents.includes(agent) || group.agents.includes('*'));
  const rules = applicable.flatMap(group => group.rules).filter(rule => path.startsWith(rule.path || '/')).sort((a,b) => (b.path || '').length - (a.path || '').length);
  const winner = rules[0];
  const allowed = !winner || winner.type === 'allow' || winner.path === '';
  const sitemaps = [...text.matchAll(/^sitemap:\s*(.+)$/gim)].map(match => match[1].trim());
  $('#robots-results').innerHTML = result(allowed ? 'pass' : 'fail', agent, allowed ? `Allowed for ${path}` : `Blocked by ${winner.path}`) + result(sitemaps.length ? 'pass' : 'warn', 'Sitemap directives', sitemaps.join(', ') || 'None found') + result(groups.length ? 'pass' : 'warn', 'Rule groups', String(groups.length));
});
function renderRedirect(data, target=$('#redirect-results')) {
  const report = data.report || data;
  const hops = report.hops || [];
  target.innerHTML = `<h3>${escapeHtml(report.requested_url || 'Redirect chain')}</h3>${hops.map((hop,index) => result(hop.status >= 300 && hop.status < 400 ? 'warn' : hop.status === 200 ? 'pass' : 'fail', `Hop ${index + 1}: HTTP ${hop.status}`, `${hop.url}${hop.resolved_location ? ' → ' + hop.resolved_location : ''}`)).join('') || '<p>No hops found.</p>'}`;
}
$('#analyze-redirect').addEventListener('click', event => {
  event.preventDefault();
  try { renderRedirect(JSON.parse($('#redirect-json').value)); }
  catch (error) { $('#redirect-results').innerHTML = result('fail', 'Invalid JSON', error.message); }
});

// Local live workbench. The hosted GitHub Pages copy remains static; the same
// files become live when served by `seo-index serve` from localhost.
const localHosts = new Set(['127.0.0.1', 'localhost', '::1', '[::1]']);
const localToken = new URLSearchParams(location.search).get('token') || sessionStorage.getItem('seoIndexToken') || '';
if (localToken) sessionStorage.setItem('seoIndexToken', localToken);
const localMode = localHosts.has(location.hostname) && Boolean(localToken);
let liveData = null;
let graphLabels = true;
let graphNodes = [];
let graphEdges = [];

async function localRequest(path, options={}) {
  const headers = {...(options.headers || {}), 'X-SEO-Index-Token': localToken};
  if (options.body) headers['Content-Type'] = 'application/json';
  const response = await fetch(path, {...options, headers});
  const data = await response.json().catch(() => ({error:`HTTP ${response.status}`}));
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}
function setLocalStatus(state, label, copy) {
  const dot = $('#local-api-dot');
  dot.classList.remove('online','offline');
  if (state) dot.classList.add(state);
  $('#local-api-label').textContent = label;
  $('#local-api-copy').textContent = copy;
}
async function checkLocalApi() {
  const button = $('#run-live-links');
  if (!localMode) {
    button.disabled = true;
    setLocalStatus('offline', 'Hosted preview mode', 'Run seo-index serve to open a localhost copy with live audits enabled.');
    return;
  }
  try {
    const health = await localRequest('/api/health');
    button.disabled = false;
    setLocalStatus('online', `Local API online · v${health.version}`, 'Live requests stay between this browser and the localhost toolkit.');
  } catch (error) {
    button.disabled = true;
    setLocalStatus('offline', 'Local API unavailable', error.message);
  }
}

function prepareGraph(data) {
  const pageList = (data.pages || []).slice().sort((a,b) => (b.pagerank || 0) - (a.pagerank || 0)).slice(0, 260);
  const keep = new Set(pageList.map(page => page.final_url));
  graphNodes = pageList.map((page,index) => ({...page, x:Math.cos(index / Math.max(1,pageList.length) * Math.PI * 2) * 210, y:Math.sin(index / Math.max(1,pageList.length) * Math.PI * 2) * 210, vx:0, vy:0}));
  graphEdges = (data.edges || []).filter(edge => !edge.external && keep.has(edge.source) && keep.has(edge.resolved_target || edge.target));
  const map = new Map(graphNodes.map(node => [node.final_url,node]));
  for (let step=0; step<70; step++) {
    for (let i=0; i<graphNodes.length; i++) {
      for (let j=i+1; j<graphNodes.length; j++) {
        const a=graphNodes[i], b=graphNodes[j], dx=a.x-b.x, dy=a.y-b.y, d2=dx*dx+dy*dy+30, force=260/d2;
        a.vx += dx*force; a.vy += dy*force; b.vx -= dx*force; b.vy -= dy*force;
      }
    }
    graphEdges.forEach(edge => {
      const a=map.get(edge.source), b=map.get(edge.resolved_target || edge.target); if(!a||!b) return;
      const dx=b.x-a.x, dy=b.y-a.y, distance=Math.hypot(dx,dy)||1, force=(distance-85)*.0013;
      a.vx += dx*force; a.vy += dy*force; b.vx -= dx*force; b.vy -= dy*force;
    });
    graphNodes.forEach(node => { node.vx += -node.x*.0009; node.vy += -node.y*.0009; node.vx*=.82; node.vy*=.82; node.x+=node.vx; node.y+=node.vy; });
  }
  drawLiveGraph();
}
function drawLiveGraph() {
  const canvas = $('#live-graph'); if (!canvas) return;
  const box = canvas.getBoundingClientRect(), ratio = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.floor(box.width * ratio));
  canvas.height = Math.max(1, Math.floor(box.height * ratio));
  const context = canvas.getContext('2d'); context.setTransform(ratio,0,0,ratio,0,0); context.clearRect(0,0,box.width,box.height);
  if (!graphNodes.length) return;
  const xs=graphNodes.map(n=>n.x), ys=graphNodes.map(n=>n.y), minX=Math.min(...xs), maxX=Math.max(...xs), minY=Math.min(...ys), maxY=Math.max(...ys);
  const scale=Math.min((box.width-70)/Math.max(1,maxX-minX),(box.height-70)/Math.max(1,maxY-minY),1.4);
  const tx=box.width/2-(minX+maxX)/2*scale, ty=box.height/2-(minY+maxY)/2*scale;
  const map=new Map(graphNodes.map(node=>[node.final_url,node]));
  context.strokeStyle='rgba(184,108,255,.18)'; context.lineWidth=1;
  graphEdges.forEach(edge=>{const a=map.get(edge.source),b=map.get(edge.resolved_target || edge.target);if(!a||!b)return;context.beginPath();context.moveTo(a.x*scale+tx,a.y*scale+ty);context.lineTo(b.x*scale+tx,b.y*scale+ty);context.stroke();});
  graphNodes.forEach(node=>{const x=node.x*scale+tx,y=node.y*scale+ty,r=3.5+Math.sqrt(node.pagerank||0)*.5;context.fillStyle=!node.status||node.status>=400?'#ff7188':node.noindex?'#ffd76a':'#70f5a4';context.beginPath();context.arc(x,y,r,0,Math.PI*2);context.fill();if(graphLabels&&graphNodes.length<130){context.fillStyle='#f8f4ff';context.font='10px system-ui';let label='/';try{label=new URL(node.final_url).pathname||'/';}catch{}context.fillText(label.slice(0,34),x+r+3,y+3);}});
}
function renderLiveFindings(data) {
  const findings = data.findings || {};
  $('#live-findings').innerHTML = Object.entries(findings).filter(([,items]) => Array.isArray(items) && items.length).map(([key,items]) => `
    <details class="finding-card"><summary><span>${escapeHtml(key.replace(/([A-Z])/g,' $1'))}</span><b>${items.length}</b></summary><pre>${escapeHtml(JSON.stringify(items.slice(0,75),null,2))}</pre></details>`).join('') || '<div class="panel results"><p>No flagged site-graph findings.</p></div>';
}
$('#live-links-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (!localMode) return;
  const button=$('#run-live-links'), note=$('#live-run-note');
  button.disabled=true; button.textContent='Mapping site…'; note.classList.add('live-loading'); note.textContent='The crawl is running locally. Larger sites can take several minutes.';
  $('#live-findings').innerHTML=''; $('#live-summary').innerHTML='<p>Building site inventory and relationship graph…</p>';
  try {
    const payload={url:$('#live-url').value.trim(),sitemap:$('#live-sitemap').value.trim()||null,maxPages:Number($('#live-max-pages').value),maxDepth:Number($('#live-max-depth').value),delayMs:Number($('#live-delay').value),robotsAgent:$('#live-agent').value,includeSubdomains:$('#live-subdomains').checked,dropQuery:$('#live-drop-query').checked};
    liveData=await localRequest('/api/links',{method:'POST',body:JSON.stringify(payload)});
    renderLinkSummary(liveData,$('#live-summary')); renderLiveFindings(liveData); prepareGraph(liveData);
    note.textContent=`Completed ${liveData.summary.pagesCrawled} pages with ${liveData.summary.internalEdges} internal edges.`;
  } catch(error) {
    $('#live-summary').innerHTML=`<p class="status fail">${escapeHtml(error.message)}</p>`; note.textContent='The live crawl did not complete.';
  } finally {
    button.disabled=false; button.textContent='Run Internal Link Graph'; note.classList.remove('live-loading');
  }
});
$('#fit-live-graph').addEventListener('click',drawLiveGraph);
$('#toggle-live-labels').addEventListener('click',()=>{graphLabels=!graphLabels;drawLiveGraph();});
addEventListener('resize',()=>{if(liveData)drawLiveGraph();});
checkLocalApi();

// Professional application routing and responsive navigation.
(() => {
  const pageTitles = {
    overview: 'Overview',
    graph: 'Site graph',
    tools: 'Audit tools',
    scoring: 'Scoring models',
    reports: 'Reports',
    lab: 'Browser lab'
  };
  const validRoutes = new Set(Object.keys(pageTitles));
  const routeFromHash = () => {
    const value = location.hash.replace(/^#\/?/, '').split(/[?#]/)[0];
    return validRoutes.has(value) ? value : 'overview';
  };
  const renderRoute = () => {
    const route = routeFromHash();
    document.querySelectorAll('[data-page]').forEach(page => page.classList.toggle('active', page.dataset.page === route));
    document.querySelectorAll('[data-route-link]').forEach(link => {
      const active = link.dataset.routeLink === route;
      link.classList.toggle('active', active);
      if (active) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
    });
    const title = document.querySelector('#route-title');
    if (title) title.textContent = pageTitles[route];
    document.title = `${pageTitles[route]} · SEO-INDEX VariScripts`;
    document.body.classList.remove('nav-open');
    const toggle = document.querySelector('#nav-toggle');
    if (toggle) toggle.setAttribute('aria-expanded', 'false');
    window.scrollTo({top: 0, behavior: 'instant'});
  };
  window.addEventListener('hashchange', renderRoute);
  renderRoute();

  const toggle = document.querySelector('#nav-toggle');
  const scrim = document.querySelector('#nav-scrim');
  const toggleNav = () => {
    const open = document.body.classList.toggle('nav-open');
    if (toggle) toggle.setAttribute('aria-expanded', String(open));
  };
  if (toggle) toggle.addEventListener('click', toggleNav);
  if (scrim) scrim.addEventListener('click', toggleNav);
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && document.body.classList.contains('nav-open')) toggleNav();
  });

  const environmentLabel = document.querySelector('#environment-label');
  if (environmentLabel) {
    const local = ['127.0.0.1', 'localhost', '::1'].includes(location.hostname);
    environmentLabel.textContent = local ? 'Local live mode' : 'Hosted mode';
  }
})();
