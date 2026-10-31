const state = { investigation: null, tab: 'trace', selectedPath: null, selectedNode: null, selectedEdge: null, scale: 1, selectedScenario: null };
const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));

async function api(path, options) {
  const res = await fetch(path, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || body.error || `HTTP ${res.status}`);
  return body;
}

async function health() {
  try { const h = await api('/api/health'); $('#connection').innerHTML = `<span class="dot ok"></span><span>Connected · ${esc(h.graph)}</span>`; }
  catch { $('#connection').innerHTML = '<span class="dot bad"></span><span>FalkorDB unavailable</span>'; }
}

function setDomain(domain) { $('#domain').value = domain; document.querySelectorAll('.world-item').forEach(b => b.classList.toggle('selected', b.dataset.domain === domain)); }

function goHome() {
  state.investigation = null;
  state.selectedPath = null;
  state.selectedNode = null;
  state.selectedEdge = null;
  state.scale = 1;
  state.selectedScenario = null;
  $('#empty').classList.remove('hidden');
  $('#workspace').classList.add('hidden');
  $('#question').value = '';
  $('#investigate').disabled = true;
  $('#investigate').textContent = 'Choose an investigation';
  document.querySelectorAll('.scenario').forEach(b => b.classList.remove('selected'));
  setDomain('software');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

document.querySelectorAll('.world-item').forEach(b => b.onclick = () => { setDomain(b.dataset.domain); });
document.querySelectorAll('[data-example]').forEach(b => b.onclick = () => {
  $('#question').value = b.dataset.example;
  setDomain(b.dataset.domain);
  state.selectedScenario = b.dataset.example;
  document.querySelectorAll('.scenario').forEach(s => s.classList.toggle('selected', s === b));
  $('#investigate').disabled = false;
  $('#investigate').textContent = 'Start investigation';
});
$('#investigate').onclick = start;
$('#home').onclick = goHome;
$('#home-crumb').onclick = goHome;

async function start() {
  const question = $('#question').value.trim(); const domain = $('#domain').value;
  if (!question) return;
  $('#investigate').disabled = true; $('#investigate').textContent = 'Investigating…';
  try {
    const result = await api('/api/investigations', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({question, domain}) });
    state.investigation = result; state.selectedPath = result.paths[0]?.id || null; state.tab = 'trace';
    render();
  } catch (err) { showError(err.message); }
  finally { $('#investigate').disabled = false; $('#investigate').textContent = 'Start investigation'; }
}

function render() {
  const x = state.investigation; $('#empty').classList.add('hidden'); $('#workspace').classList.remove('hidden');
  $('#question-view').textContent = x.question; $('#domain-view').textContent = x.domain.replace('-', ' ').replace(/\b\w/g, c => c.toUpperCase()); $('#target-view').textContent = x.target || 'No target';
  $('#domain-crumb').textContent = $('#domain-view').textContent; $('#target-crumb').textContent = x.target || 'Investigation';
  const status = x.status.replaceAll('_',' '); $('#status-badge').textContent = status; $('#status-badge').className = `status-badge ${x.status.toLowerCase()}`;
  const outcome = x.competition?.outcome;
  $('#verdict-state').textContent = outcome || (x.target ? 'RESULT' : 'FAILED');
  $('#verdict').textContent = x.verdict || (x.target ? 'Investigation completed' : 'Outcome not found');
  $('#verdict-detail').textContent = outcome === 'INSUFFICIENT' ? 'Continuum could not establish a supported explanation.' : outcome === 'AMBIGUOUS' ? 'Multiple graph-derived explanations remain plausible; the evidence does not justify selecting one.' : x.report?.most_supported_explanation || 'Inspect the graph and evidence below.';
  $('#path-count').textContent = `${x.paths.length} paths · ${x.evidence.length} evidence records`;
  renderPathList(); renderGraph(); renderTab();
}

function pathClass(p) { if (p.id === state.selectedPath) return 'path-selected'; if (p.temporally_valid === false) return 'path-rejected'; if (p.missing_evidence_count) return 'path-unknown'; return 'path-alt'; }
function renderPathList(){ const x=state.investigation; $('#path-list').innerHTML=x.paths.map((p,i)=>`<button class="path-chip ${pathClass(p)} ${p.id===state.selectedPath?'active':''}" data-path="${esc(p.id)}"><span>${i+1}</span>${p.node_ids[0]} → ${p.node_ids[p.node_ids.length-1]}<small>${p.temporal_status}${p.missing_evidence_count?' · missing evidence':''}</small></button>`).join('') || '<span class="muted-block">No candidate paths recovered.</span>'; $('#path-list').querySelectorAll('[data-path]').forEach(b=>b.onclick=()=>{state.selectedPath=b.dataset.path;state.selectedNode=null;state.selectedEdge=null;renderPathList();renderGraph()}); }
function renderGraph() {
  const x = state.investigation, el = $('#graph');
  const paths = x.paths.filter(p => p.temporally_valid !== false || p.id === state.selectedPath);
  const path = x.paths.find(p => p.id === state.selectedPath) || paths[0];
  if (!path) { el.innerHTML = '<div class="graph-empty">No graph path was recovered.</div>'; return; }
  const nodeIds = [...new Set(path.node_ids)];
  const width = Math.max(780, nodeIds.length * 180), height = 270;
  const positions = Object.fromEntries(nodeIds.map((id,i) => [id, {x:80+i*((width-160)/Math.max(1,nodeIds.length-1)), y:130}]));
  let svg = `<svg viewBox="0 0 ${width} ${height}" role="img" style="transform:scale(${state.scale})"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z"/></marker></defs>`;
  path.relationships.forEach((rel,i) => { const a=positions[path.node_ids[i]], b=positions[path.node_ids[i+1]]; const edgeId=path.edge_ids[i]; const selected=state.selectedEdge===edgeId; svg += `<g class="edge ${selected?'edge-selected':''}" tabindex="0" data-edge="${esc(edgeId)}"><line x1="${a.x+58}" y1="${a.y}" x2="${b.x-58}" y2="${b.y}" marker-end="url(#arrow)"/><text x="${(a.x+b.x)/2}" y="${a.y-12}" text-anchor="middle">${esc(rel)}</text></g>`; });
  nodeIds.forEach(id => { const p=positions[id], rec=x.graph.nodes.find(n=>n.id===id)||{}; const selected=state.selectedNode===id; svg += `<g class="node ${selected?'node-selected':''}" tabindex="0" data-node="${esc(id)}"><rect x="${p.x-58}" y="${p.y-28}" width="116" height="56" rx="10"/><text x="${p.x}" y="${p.y-3}" text-anchor="middle">${esc(rec.label||'Node')}</text><text x="${p.x}" y="${p.y+14}" text-anchor="middle" class="node-id">${esc(id)}</text></g>`; });
  svg += '</svg>'; el.innerHTML = svg;
  el.querySelectorAll('[data-node]').forEach(n => { n.onclick=()=>inspectNode(n.dataset.node); n.onkeydown=e=>{if(e.key==='Enter')inspectNode(n.dataset.node)}; });
  el.querySelectorAll('[data-edge]').forEach(n => { n.onclick=()=>inspectEdge(n.dataset.edge); n.onkeydown=e=>{if(e.key==='Enter')inspectEdge(n.dataset.edge)}; });
}

function inspectNode(id) { state.selectedNode=id; state.selectedEdge=null; const n=state.investigation.graph.nodes.find(v=>v.id===id)||{}; $('#inspector').innerHTML=`<div class="panel-kicker">NODE</div><h3>${esc(n.name||id)}</h3><div class="mono">${esc(id)}</div><dl>${Object.entries(n).filter(([k])=>!['id','name'].includes(k)).map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(typeof v==='object'?JSON.stringify(v):v)}</dd>`).join('')}</dl>`; renderGraph(); }
function inspectEdge(id) { state.selectedEdge=id; state.selectedNode=null; const e=state.investigation.graph.edges.find(v=>v.edge_id===id)||{}; $('#inspector').innerHTML=`<div class="panel-kicker">RELATIONSHIP</div><h3>${esc(e.relationship||'Relationship')}</h3><div class="mono">${esc(id)}</div><dl>${Object.entries(e).filter(([k])=>k!=='edge_id').map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(typeof v==='object'?JSON.stringify(v):v)}</dd>`).join('')}</dl>`; renderGraph(); }

function renderTab() {
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active',t.dataset.tab===state.tab));
  const x=state.investigation; let html='';
  if(state.tab==='trace') html=x.trace.map((t,i)=>`<div class="trace-row"><span>${String(i+1).padStart(2,'0')}</span><code>${esc(t)}</code></div>`).join('') || '<div class="muted-block">No trace events were returned.</div>';
  if(state.tab==='evidence') html=x.evidence.map(e=>`<button class="evidence-row" onclick="inspectEvidence('${esc(e.id)}')"><span class="evidence-status">${esc(e.status)}</span><span>${esc(e.id)}</span><span>${esc(e.source_id)}</span></button>`).join('') || '<div class="muted-block">No evidence records were returned.</div>';
  if(state.tab==='hypotheses') html=x.hypotheses.map(h=>`<div class="hypothesis"><div class="hyp-head"><strong>${esc(h.id)}</strong><span class="score">score ${esc(h.score)}</span></div><div>${esc(h.claim)}</div><div class="hyp-meta">${esc(h.path_quality)} · support ${esc(h.support_count)} · contradictions ${esc(h.contradiction_count)} · missing ${esc(h.missing_evidence_count)}</div></div>`).join('') || '<div class="muted-block">No hypothesis competition was possible because no candidate paths were recovered.</div>';
  $('#tab-content').innerHTML=html;
}
window.inspectEvidence = function(id){ const e=state.investigation.evidence.find(v=>v.id===id); if(!e)return; $('#inspector').innerHTML=`<div class="panel-kicker">EVIDENCE</div><h3>${esc(e.id)}</h3><div class="evidence-status large">${esc(e.status)}</div><dl><dt>Source</dt><dd>${esc(e.source_id)}</dd><dt>Observed</dt><dd>${esc(e.observed_at||'—')}</dd><dt>Record</dt><dd>${esc(e.record||'—')}</dd><dt>Span</dt><dd>${esc(e.span||'—')}</dd></dl>`; };

document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{state.tab=t.dataset.tab;renderTab()});
$('#zoom-in').onclick=()=>{state.scale=Math.min(1.3,state.scale+.1);renderGraph()}; $('#zoom-out').onclick=()=>{state.scale=Math.max(.7,state.scale-.1);renderGraph()}; $('#fit').onclick=()=>{state.scale=1;renderGraph()};
health();
