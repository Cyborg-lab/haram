const tg = window.Telegram?.WebApp;
if (tg) { tg.ready(); tg.expand(); }
const initData = tg?.initData || '';
const headers = { 'Content-Type': 'application/json', 'X-Telegram-Init-Data': initData };
let me = null;

const toast = text => { const el = document.querySelector('#toast'); el.textContent = text; el.style.display = 'block'; setTimeout(() => el.style.display = 'none', 2600); };
const request = async (url, options = {}) => {
  const res = await fetch(url, { ...options, headers: { ...headers, ...(options.headers || {}) } });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Xatolik yuz berdi');
  return res.json();
};
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
function card(ad, own = false) {
  const image = ad.image_data ? `<img src="${ad.image_data}" alt="${esc(ad.model)}">` : '';
  return `<article class="card">${image}<span class="muted">${ad.is_active ? '🟢 Aktiv' : '🔴 Noaktiv'}</span><h3>${esc(ad.brand)} ${esc(ad.model)}</h3><p class="muted">${esc(ad.storage)} · ${esc(ad.ram)}<br>${esc(ad.camera)} kamera · ${esc(ad.screen)} · ${esc(ad.battery)}<br>${esc(ad.condition)}</p><p class="price">${esc(ad.price)}</p><p>${esc(ad.description)}</p><p class="muted">📞 ${esc(ad.phone)}</p>${own ? `<button class="status" data-id="${ad.id}">${ad.is_active ? '🔴 Noaktiv qilish' : '🟢 Aktiv qilish'}</button>` : ''}</article>`;
}
async function loadMarket() { const ads = await request('/api/ads?q=' + encodeURIComponent(document.querySelector('#search').value)); document.querySelector('#ads').innerHTML = ads.length ? ads.map(card).join('') : '<p>Aktiv e’lon topilmadi.</p>'; }
async function loadMine() { const ads = await request('/api/my-ads'); const root = document.querySelector('#myAds'); root.innerHTML = ads.length ? ads.map(a => card(a, true)).join('') : '<p>Sizda hali e’lon yo‘q.</p>'; document.querySelectorAll('.status').forEach(b => b.onclick = async () => { try { await request(`/api/my-ads/${b.dataset.id}/status`, { method: 'PATCH' }); await loadMine(); toast('E’lon holati yangilandi'); } catch(e) { toast(e.message); } }); }
function openView(name) { document.querySelectorAll('.view,.tab').forEach(e => e.classList.remove('active')); document.querySelector('#' + name).classList.add('active'); document.querySelector(`[data-view="${name}"]`).classList.add('active'); if (name === 'mine') loadMine().catch(e => toast(e.message)); }

document.querySelectorAll('.tab').forEach(b => b.onclick = () => openView(b.dataset.view));
document.querySelector('#searchBtn').onclick = () => loadMarket().catch(e => toast(e.message));
document.querySelector('#search').onkeydown = e => { if (e.key === 'Enter') loadMarket().catch(err => toast(err.message)); };
document.querySelector('#profileBtn').onclick = () => { document.querySelector('#userName').textContent = me?.name || ''; document.querySelector('#phone').value = me?.phone || ''; document.querySelector('#profile').showModal(); };
document.querySelector('#saveProfile').onclick = async e => { e.preventDefault(); try { await request('/api/me', { method: 'PUT', body: JSON.stringify({ phone: document.querySelector('#phone').value }) }); me.phone = document.querySelector('#phone').value; document.querySelector('#profile').close(); toast('Profil saqlandi'); } catch (err) { toast(err.message); } };
document.querySelector('#adForm').onsubmit = async e => { e.preventDefault(); try { const f = new FormData(e.target); const payload = Object.fromEntries(f.entries()); const file = document.querySelector('#image').files[0]; if (file) payload.image_data = await new Promise((ok, no) => { const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = no; r.readAsDataURL(file); }); await request('/api/ads', { method: 'POST', body: JSON.stringify(payload) }); e.target.reset(); toast('E’lon aktiv holatda joylandi'); openView('mine'); } catch (err) { toast(err.message); if (err.message.includes('telefon')) document.querySelector('#profile').showModal(); } };

(async () => { if (!initData) toast('Mini App faqat Telegram ichidan ochiladi'); try { me = await request('/api/me'); await loadMarket(); } catch (e) { toast(e.message); } })();
