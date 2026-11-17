const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money = value => `₹${Number(value).toLocaleString('en-IN')}`;
let state = { user: null, requests: [], audit: [], metrics: {} };
let selectedId = null;

async function api(path, options = {}) {
  const response = await fetch(path, { credentials: 'same-origin', ...options, headers: { 'Content-Type': 'application/json', ...(options.headers || {}) } });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Request failed: ${response.status}`);
  return data;
}

function toast(text, error = false) {
  const node = $('#toast'); node.textContent = text; node.style.background = error ? '#953e34' : '#243b3c'; node.classList.add('show');
  clearTimeout(toast.timer); toast.timer = setTimeout(() => node.classList.remove('show'), 3500);
}

function showApp(user) {
  $('#login-screen').hidden = true; $('#app').hidden = false;
  $('#current-role').textContent = `${user.name} · ${user.role.replaceAll('_', ' ')}`;
  $('#welcome-name').textContent = user.name;
  $('#welcome-role').textContent = `${user.department} / ${user.role.replaceAll('_', ' ')}`;
  $('#new-request').hidden = user.role !== 'employee';
}

function showLogin() { $('#app').hidden = true; $('#login-screen').hidden = false; selectedId = null; }

function routeStep(label, index, item) {
  const name = label.replaceAll('_', ' ');
  const css = item.stage_index > index ? 'done' : item.stage === label ? 'current' : '';
  return `<span class="route-step ${css}">${index + 1}. ${esc(name)}</span>`;
}

function renderList() {
  const query = $('#search').value.trim().toLowerCase();
  const filter = $('#filter').value;
  const items = state.requests.filter(item => (!filter || item.status === filter) &&
    (!query || `${item.id} req-${String(item.id).padStart(4,'0')} ${item.title} ${item.requester}`.toLowerCase().includes(query)));
  $('#request-list').innerHTML = items.length ? items.map(item => `<button class="request-item ${item.id === selectedId ? 'selected' : ''}" type="button" data-id="${item.id}"><span><span class="id">REQ-${String(item.id).padStart(4,'0')}</span><strong>${esc(item.title)}</strong><small>${esc(item.requester)} · ${esc(item.department)}</small></span><span class="right"><strong>${money(item.amount)}</strong><span class="pill ${item.status.toLowerCase()}">${esc(item.status)}</span></span></button>`).join('') : '<div class="empty-detail"><p>No requests in this view.</p></div>';
}

function renderActivity() {
  $('#activity').innerHTML = state.audit.slice(0, 5).map(row => `<div class="activity-row"><b>REQ-${String(row.request_id).padStart(4,'0')}</b> · ${esc(row.action.replaceAll('_', ' '))}<small>${esc(row.actor)} · ${new Date(row.at).toLocaleDateString('en-IN')}</small></div>`).join('') || '<div class="activity-row">No activity yet.</div>';
}

async function refresh() {
  state = await api('/api/state');
  showApp(state.user);
  for (const key of ['visible', 'pending', 'incomplete', 'overdue']) $(`#m-${key}`).textContent = state.metrics[key];
  renderList(); renderActivity();
  if (selectedId && state.requests.some(item => item.id === selectedId)) await showDetail(selectedId);
}

async function showDetail(id) {
  const data = await api(`/api/requests/${id}`);
  selectedId = Number(id);
  renderList();
  const item = data.request;
  const stage = item.status === 'Approved' || item.status === 'Rejected' ? item.status : item.stage.replaceAll('_', ' ');
  $('#detail').innerHTML = `<div class="detail-top"><div><span class="eyebrow">REQ-${String(item.id).padStart(4,'0')} · ${esc(item.status.toUpperCase())}</span><h3>${esc(item.title)}</h3><small>Requested by ${esc(item.requester)} · ${esc(item.department)}</small></div><div class="detail-amount">${money(item.amount)}</div></div>
    <div class="detail-grid"><div><span>CURRENT STEP</span><b>${esc(stage)}</b></div><div><span>DOCUMENTS</span><b>${item.has_docs ? 'Confirmed' : 'Missing'}</b></div><div><span>TARGET DATE</span><b>${new Date(item.due_at).toLocaleDateString('en-IN')}${item.overdue ? ' · Late' : ''}</b></div></div>
    <div class="detail-section"><h4>Business justification</h4><p>${esc(item.justification)}</p></div>
    <div class="detail-section"><h4>Required approval route</h4><div class="route">${item.route.map((role, i) => routeStep(role, i, item)).join('')}</div></div>
    <div class="detail-section"><h4>✳ Rule-based policy review</h4><div class="risk">${item.hints.map(hint => `<p>• ${esc(hint)}</p>`).join('')}<small>For human review only · No AI approval action</small></div></div>
    ${item.can_edit_docs ? `<div class="detail-section"><h4>Complete the request</h4><p>This demo confirms document presence; it does not upload or inspect a file.</p><button class="button ghost" id="docs-button" type="button">Mark supporting document present →</button></div>` : ''}
    ${item.can_decide ? `<div class="detail-section"><h4>Your decision is needed</h4><p>Review the business need, document status and route. Your action is recorded in the audit trail.</p><form id="decision-form" class="decision-form"><textarea name="note" maxlength="500" placeholder="Decision note (required for rejection)"></textarea><div class="decision-actions"><button class="button dark" type="submit" data-decision="approve">Approve this step →</button><button class="button danger" type="submit" data-decision="reject">Reject request</button></div></form></div>` : ''}
    <div class="detail-section"><h4>Audit history</h4>${data.audit.map(row => `<div class="audit-item"><div><strong>${esc(row.action.replaceAll('_', ' '))} · ${esc(row.actor)}</strong><small>${esc(row.note)} · ${new Date(row.at).toLocaleString('en-IN')}</small></div></div>`).join('')}</div>`;
}

function routePreview() {
  const amount = Number($('#create-form').elements.amount.value || 0);
  const docs = $('#create-form').elements.has_docs.checked;
  const route = amount <= 25000 ? 'Manager' : amount <= 100000 ? 'Manager → Finance' : 'Manager → Finance → Department head';
  $('#route-preview').textContent = amount > 0 ? `Required route: ${route}. ${docs ? 'Documents confirmed in demo.' : 'Request will wait for documents.'}` : 'Enter an amount to see the required approval route.';
}

$('#login-form').addEventListener('submit', async event => {
  event.preventDefault(); $('#login-error').textContent = '';
  const data = Object.fromEntries(new FormData(event.target));
  try { await api('/api/login', { method: 'POST', body: JSON.stringify(data) }); await refresh(); }
  catch (error) { $('#login-error').textContent = error.message; }
});
$('#logout').addEventListener('click', async () => { try { await api('/api/logout', { method: 'POST', body: '{}' }); } finally { showLogin(); } });
$('#new-request').addEventListener('click', () => { routePreview(); $('#create-dialog').showModal(); });
$('#close-create').addEventListener('click', () => $('#create-dialog').close());
$('#create-form').elements.amount.addEventListener('input', routePreview);
$('#create-form').elements.has_docs.addEventListener('change', routePreview);
$('#create-form').addEventListener('submit', async event => {
  event.preventDefault(); const data = Object.fromEntries(new FormData(event.target));
  data.amount = Number(data.amount); data.has_docs = event.target.elements.has_docs.checked;
  try { const result = await api('/api/requests', { method: 'POST', body: JSON.stringify(data) }); $('#create-dialog').close(); event.target.reset(); await refresh(); await showDetail(result.id); toast('Request created. The route is recorded.'); }
  catch (error) { toast(error.message, true); }
});
$('#request-list').addEventListener('click', event => { const row = event.target.closest('[data-id]'); if (row) showDetail(row.dataset.id).catch(e => toast(e.message, true)); });
$('#search').addEventListener('input', renderList); $('#filter').addEventListener('change', renderList);
$('#detail').addEventListener('click', async event => {
  if (event.target.closest('#docs-button')) {
    try { await api(`/api/requests/${selectedId}/documents`, { method: 'POST', body: JSON.stringify({ has_docs: true }) }); await refresh(); toast('Document presence confirmed; manager review is next.'); }
    catch (error) { toast(error.message, true); }
  }
});
$('#detail').addEventListener('submit', async event => {
  if (event.target.id !== 'decision-form') return;
  event.preventDefault(); const decision = event.submitter?.dataset.decision;
  const note = new FormData(event.target).get('note');
  try { await api(`/api/requests/${selectedId}/decision`, { method: 'POST', body: JSON.stringify({ decision, note }) }); await refresh(); toast('Decision recorded in the audit history.'); }
  catch (error) { toast(error.message, true); }
});
$('#ask-form').addEventListener('submit', async event => {
  event.preventDefault();
  try { const result = await api('/api/assistant', { method: 'POST', body: JSON.stringify({ question: $('#ask-input').value }) }); $('#ask-answer').textContent = result.answer; }
  catch (error) { toast(error.message, true); }
});
api('/api/me').then(result => { showApp(result.user); return refresh(); }).catch(showLogin);
