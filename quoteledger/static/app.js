const state = {requests: [], activeId: null, detail: null, reviewId: null};
const $ = id => document.getElementById(id);
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const money = value => value == null ? '—' : `R ${Number(value).toLocaleString('en-ZA', {minimumFractionDigits:2, maximumFractionDigits:2})}`;
const toast = message => { const el = $('toast'); el.textContent = message; el.classList.add('show'); clearTimeout(toast.timer); toast.timer = setTimeout(() => el.classList.remove('show'), 3000); };
async function api(path, options = {}) {
  const response = await fetch(path, {headers: {'Content-Type': 'application/json'}, ...options});
  const data = await response.json();
  if (!response.ok) throw Error(data.error || 'Something went wrong');
  return data;
}
async function loadRequests() {
  const data = await api('/api/requests'); state.requests = data.requests;
  $('request-count').textContent = state.requests.length;
  $('requests').innerHTML = state.requests.map(r => `<button class="request-card ${r.id === state.activeId ? 'selected' : ''}" data-request="${r.id}"><strong>${escapeHtml(r.name)}</strong><small>${Number(r.quantity).toLocaleString('en-ZA')} boxes · ${new Date(r.created_at).toLocaleDateString('en-ZA')}</small></button>`).join('') || '<div class="empty-state">No requests yet.</div>';
  document.querySelectorAll('[data-request]').forEach(el => el.addEventListener('click', () => selectRequest(Number(el.dataset.request))));
}
async function selectRequest(id) {
  state.activeId = id;
  state.detail = await api(`/api/requests/${id}`);
  await loadRequests(); renderDetail();
}
function renderDetail() {
  const {request:r, quotes, comparison:rows} = state.detail;
  const reviewed = quotes.filter(q => q.status === 'reviewed').length;
  const comparable = rows.filter(row => row.comparable && row.status === 'reviewed').length;
  const best = rows.find(row => row.lowest_reviewed);
  $('detail').innerHTML = `<div class="detail-head"><div><span class="eyebrow">QUOTE COMPARISON #${r.id}</span><h2>${escapeHtml(r.name)}</h2><p class="detail-sub">Created ${new Date(r.created_at).toLocaleDateString('en-ZA', {day:'numeric',month:'long',year:'numeric'})}</p></div><div class="head-actions"><a class="button secondary" href="/api/requests/${r.id}/export.csv" download="comparison-${r.id}.csv">Export CSV</a><button class="button primary" id="add-quote">+ Add supplier quote</button></div></div>
    ${r.specification ? `<p class="spec">${escapeHtml(r.specification)}</p>` : ''}
    <div class="metrics"><div class="metric"><small>Required quantity</small><strong>${Number(r.quantity).toLocaleString('en-ZA')}</strong></div><div class="metric"><small>Quotes reviewed</small><strong>${reviewed} / ${quotes.length}</strong></div><div class="metric"><small>Lowest reviewed total</small><strong>${best ? money(best.landed_total_zar) : '—'}</strong></div></div>
    <div class="table-head"><h3>Supplier comparison</h3><span class="count">${comparable} comparable</span></div>
    <div class="table-wrap"><table><thead><tr><th>Supplier</th><th>Price / box</th><th>Order qty</th><th>Landed total</th><th>Lead time</th><th>Status</th><th></th></tr></thead><tbody>${rows.map(row => `<tr><td class="supplier-cell"><strong>${escapeHtml(row.supplier)}</strong><small>${escapeHtml(row.currency || 'Currency missing')}</small></td><td>${money(row.unit_price_zar)}</td><td>${Number(row.order_quantity).toLocaleString('en-ZA')}</td><td><strong>${money(row.landed_total_zar)}</strong>${row.lowest_reviewed ? ' <span class="badge green">LOWEST</span>' : ''}</td><td>${row.lead_days ? `${escapeHtml(row.lead_days)} days` : '—'}</td><td><span class="badge ${row.status === 'reviewed' ? row.comparable ? 'green':'amber' : 'grey'}">${row.status === 'reviewed' ? row.comparable ? 'Reviewed':'Incomplete' : 'Needs review'}</span></td><td><button class="link-button" data-review="${row.quote_id}">Review ↗</button></td></tr>`).join('') || '<tr><td colspan="7">No quotes yet. Add the first supplier quote.</td></tr>'}</tbody></table></div>
    <div class="issues"><h3>Buyer checks</h3>${rows.flatMap(row => row.issues.map(issue => `<div class="issue-row"><b>${escapeHtml(row.supplier)}</b><span>${escapeHtml(issue)}</span></div>`)).join('') || '<p class="muted">No open checks from the current fields. Confirm the original documents before ordering.</p>'}</div>`;
  $('add-quote').onclick = () => $('quote-dialog').showModal();
  document.querySelectorAll('[data-review]').forEach(el => el.onclick = () => openReview(Number(el.dataset.review)));
}
const fieldDefs = [
  ['supplier','Supplier'],['product','Product / quoted specification'],['currency','Currency'],
  ['unit_price','Quoted price'],['price_unit','Price unit'],['pack_size','Boxes per pack'],
  ['moq','MOQ in boxes'],['lead_days','Lead time in days'],['transport_cost','Transport cost in quote currency'],
  ['payment_terms','Payment terms'],['valid_until','Valid until'],['exceptions','Exceptions / exclusions'],
  ['fx_to_zar','ZAR per 1 quoted currency'],['fx_source','Exchange rate source / date']
];
function openReview(id) {
  const quote = state.detail.quotes.find(q => q.id === id); if (!quote) return;
  state.reviewId = id;
  $('review-title').textContent = quote.fields.supplier || quote.filename || `Quote #${id}`;
  $('review-fields').innerHTML = fieldDefs.map(([key,label]) => {
    const value = escapeHtml(quote.fields[key] || '');
    const hint = quote.evidence[key] ? `title="Extracted from: ${escapeHtml(quote.evidence[key])}"` : '';
    if (key === 'currency') return `<label>${label}<select name="${key}" ${hint}><option value="">Choose currency</option>${['ZAR','USD','EUR','GBP'].map(v => `<option value="${v}" ${v===quote.fields[key]?'selected':''}>${v}</option>`).join('')}</select></label>`;
    if (key === 'price_unit') return `<label>${label}<select name="${key}" ${hint}><option value="">Choose unit</option>${[['each','Per box'],['pack','Per pack'],['100','Per 100 boxes'],['1000','Per 1,000 boxes']].map(([v,l]) => `<option value="${v}" ${v===quote.fields[key]?'selected':''}>${l}</option>`).join('')}</select></label>`;
    return `<label class="${['product','payment_terms','exceptions','fx_source'].includes(key)?'full':''}">${label}<input name="${key}" value="${value}" ${hint} ${['unit_price','pack_size','moq','lead_days','transport_cost','fx_to_zar'].includes(key)?'inputmode="decimal"':''}></label>`;
  }).join('');
  $('source-text').textContent = quote.original_text;
  $('pdf-link').hidden = !quote.filename.toLowerCase().endsWith('.pdf');
  $('pdf-link').href = `/api/quotes/${id}/source.pdf`;
  $('evidence-box').textContent = `${quote.evidence._engine || 'rules'} extraction. Hover over a suggested field to see its source line. All fields need buyer review.`;
  $('review-error').textContent = '';
  $('review-dialog').showModal();
}
document.querySelectorAll('.close-dialog').forEach(button => button.onclick = () => button.closest('dialog').close());
$('new-request').onclick = () => $('request-dialog').showModal();
$('how-it-works').onclick = () => $('help-dialog').showModal();
$('request-form').onsubmit = async event => {
  event.preventDefault(); $('request-error').textContent = '';
  const form = new FormData(event.currentTarget);
  try { const created = await api('/api/requests', {method:'POST', body:JSON.stringify(Object.fromEntries(form))}); $('request-dialog').close(); event.currentTarget.reset(); await selectRequest(created.id); toast('Purchase request created'); }
  catch (error) { $('request-error').textContent = error.message; }
};
function fileAsBase64(file) { return new Promise((resolve,reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result).split(',')[1]); reader.onerror = reject; reader.readAsDataURL(file); }); }
$('quote-form').onsubmit = async event => {
  event.preventDefault(); $('quote-error').textContent = '';
  const file = $('quote-file').files[0]; const pasted = $('quote-text').value.trim();
  if (!file && !pasted) { $('quote-error').textContent = 'Choose a file or paste quote text.'; return; }
  try {
    let body = {text:pasted, filename:''};
    if (file) {
      if (file.size > 7*1024*1024) throw Error('File must be 7 MB or smaller.');
      if (file.name.toLowerCase().endsWith('.pdf')) body = {filename:file.name,pdf_base64:await fileAsBase64(file)};
      else if (file.name.toLowerCase().endsWith('.txt')) body = {filename:file.name,text:await file.text()};
      else throw Error('Choose a PDF or TXT file.');
    }
    const quote = await api(`/api/requests/${state.activeId}/quotes`, {method:'POST',body:JSON.stringify(body)});
    $('quote-dialog').close(); event.currentTarget.reset(); await selectRequest(state.activeId); openReview(quote.id); toast('Quote added. Review its fields.');
  } catch (error) { $('quote-error').textContent = error.message; }
};
$('review-form').onsubmit = async event => {
  event.preventDefault(); $('review-error').textContent = '';
  const status = event.submitter?.dataset.status || 'needs_review';
  const fields = Object.fromEntries(new FormData(event.currentTarget));
  try { await api(`/api/quotes/${state.reviewId}`, {method:'PUT',body:JSON.stringify({fields,status})}); $('review-dialog').close(); await selectRequest(state.activeId); toast(status === 'reviewed' ? 'Quote marked reviewed' : 'Draft saved'); }
  catch (error) { $('review-error').textContent = error.message; }
};
loadRequests().then(() => { if (state.requests.length) selectRequest(state.requests[0].id); }).catch(error => toast(error.message));
