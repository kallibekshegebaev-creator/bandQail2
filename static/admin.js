// BandQil — Admin paneli (platforma egasi uchun). X-Admin-Token bilan ishlaydi.
// Mijoz ilovasi (app.js) va bron qilish mantig'iga mutlaqo tegmaydi — bu alohida, mustaqil sahifa.
(() => {
  "use strict";

  const TOKEN_KEY = "bq_admin_token";
  const app = document.getElementById("app");
  const toastEl = document.getElementById("toast");
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
  const money = (n) => Number(n || 0).toLocaleString("uz-UZ") + " so'm";
  const todayStr = () => new Date().toLocaleDateString("sv-SE"); // YYYY-MM-DD, mahalliy vaqt bo'yicha

  let toastTimer = null;
  function toast(msg) {
    toastEl.textContent = msg;
    toastEl.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toastEl.classList.remove("show"), 2600);
  }

  const S = {
    token: localStorage.getItem(TOKEN_KEY) || "",
    tab: "salons",
    districts: [],
    salons: [],
    selectedSalonId: null,
    masters: [],
    selectedMasterId: null,
    selectedMasterName: "",
    services: [],
    bookingDate: todayStr(),
    bookingSalonId: "",
    bookings: [],
  };

  async function api(path, opts = {}) {
    const res = await fetch(path, {
      ...opts,
      headers: { "Content-Type": "application/json", "X-Admin-Token": S.token, ...(opts.headers || {}) },
    });
    let data = null;
    try { data = await res.json(); } catch { /* bo'sh javob */ }
    if (!res.ok) {
      const msg = (data && (data.detail || data.message)) || `Xato (${res.status})`;
      throw new Error(msg);
    }
    return data;
  }

  const KIND_LABEL = { barbershop: "Barbershop", beauty: "Go'zallik saloni" };
  const STATUS_LABEL = { booked: "Band", done: "Bajarildi", cancelled: "Bekor qilindi", no_show: "Kelmadi" };

  function switchHtml(id, checked, extra = "") {
    return `<label class="admin-switch" ${extra}>
      <input type="checkbox" id="${id}" ${checked ? "checked" : ""}>
      <span class="admin-switch__track"></span>
    </label>`;
  }

  // ---------- 0. Kirish ----------
  function renderLogin(error) {
    app.innerHTML = `
      <div class="admin-login">
        <h1>BandQil Admin</h1>
        <p class="muted">Platformani boshqarish uchun maxfiy kalitni kiriting.</p>
        <label class="field"><span>Admin token</span>
          <input class="input" id="tok" type="password" placeholder="ADMIN_TOKEN" autocomplete="off">
        </label>
        ${error ? `<div class="admin-error">${esc(error)}</div>` : ""}
        <button class="btn" id="go">Kirish</button>
      </div>`;
    $("#tok").focus();
    $("#tok").addEventListener("keydown", (e) => { if (e.key === "Enter") $("#go").click(); });
    $("#go").addEventListener("click", async () => {
      const val = $("#tok").value.trim();
      if (!val) return;
      S.token = val;
      try {
        await api("/api/admin/salons");
        localStorage.setItem(TOKEN_KEY, val);
        boot();
      } catch (e) {
        S.token = "";
        renderLogin("Token noto'g'ri yoki serverga ulanib bo'lmadi.");
      }
    });
  }

  // ---------- qobiq: yuqori panel + tablar ----------
  const TABS = [
    ["salons", "Salonlar"],
    ["masters", "Ustalar"],
    ["services", "Xizmatlar"],
    ["bookings", "Bronlar"],
  ];

  function shell(contentHtml) {
    app.innerHTML = `
      <div class="admin-top">
        <span class="brand">BandQil <span class="muted" style="font-weight:500">· Admin</span></span>
        <button class="admin-logout" data-action="logout">Chiqish</button>
      </div>
      <nav class="admin-tabs" id="admin-tabs">
        ${TABS.map(([k, label]) => `<button data-tab="${k}" aria-current="${S.tab === k ? "page" : "false"}">${label}</button>`).join("")}
      </nav>
      <div id="view">${contentHtml}</div>`;
  }

  function loadingCard() { return `<div class="admin-card admin-empty">Yuklanmoqda…</div>`; }

  // ---------- 1. Salonlar ----------
  async function renderSalons() {
    shell(loadingCard());
    try {
      const [districts, salons] = await Promise.all([api("/api/districts"), api("/api/admin/salons")]);
      S.districts = districts; S.salons = salons;
    } catch (e) {
      shell(`<div class="admin-card admin-error">${esc(e.message)}</div>`);
      return;
    }
    const districtOptions = S.districts.map((d) => `<option value="${d.id}">${esc(d.name)}</option>`).join("");
    shell(`
      <div class="admin-card">
        <div class="admin-card__title">Tumanlar</div>
        <div class="admin-card__actions">
          ${S.districts.map((d) => `<span class="admin-chip">${esc(d.name)}</span>`).join("") || `<span class="muted small">Hali tuman qo'shilmagan</span>`}
        </div>
        <form class="admin-inline-form" id="f-district">
          <input class="input" name="name" placeholder="Yangi tuman nomi" required>
          <button class="btn btn--small btn--quiet" type="submit">+ Qo'shish</button>
        </form>
      </div>

      <div class="admin-card">
        <div class="admin-card__title">Yangi salon</div>
        <form class="admin-form admin-form--2col" id="f-salon">
          <div><label>Nomi</label><input class="input" name="name" required></div>
          <div><label>Yo'nalish</label><select class="select" name="kind" required>
            <option value="barbershop">Barbershop</option><option value="beauty">Go'zallik saloni</option>
          </select></div>
          <div><label>Tuman</label><select class="select" name="district_id" required>${districtOptions}</select></div>
          <div><label>Telefon</label><input class="input" name="phone" placeholder="+998 90 123 45 67"></div>
          <div class="span2"><label>Manzil</label><input class="input" name="address" required></div>
          <div><label>Ochilish</label><input class="input" name="open_time" type="time" value="09:00" required></div>
          <div><label>Yopilish</label><input class="input" name="close_time" type="time" value="20:00" required></div>
          <div><label>Obuna muddati (ixtiyoriy)</label><input class="input" name="paid_until" type="date"></div>
          <div class="span2"><label>Rasm havolasi (ixtiyoriy)</label><input class="input" name="photo_url" type="url" placeholder="https://..."></div>
          <div><label>Kenglik — lat (ixtiyoriy)</label><input class="input" name="lat" type="number" step="0.000001" placeholder="41.311081"></div>
          <div><label>Uzunlik — lng (ixtiyoriy)</label><input class="input" name="lng" type="number" step="0.000001" placeholder="69.240562"></div>
          <p class="small muted span2" style="margin:-6px 0 0">Lat/lng — Google Xaritada joyni bosib turib chiqadigan koordinata (masofani mijozga ko'rsatish uchun).</p>
          <div class="span2"><button class="btn" type="submit">Salon qo'shish</button></div>
        </form>
      </div>

      <div id="salon-list">${S.salons.length ? "" : `<div class="admin-card admin-empty">Hali salon yo'q</div>`}</div>
    `);

    $("#f-district").addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = new FormData(e.target).get("name").trim();
      if (!name) return;
      try { await api("/api/admin/districts", { method: "POST", body: JSON.stringify({ name }) }); toast("Tuman qo'shildi"); renderSalons(); }
      catch (err) { toast(err.message); }
    });

    $("#f-salon").addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const lat = fd.get("lat"), lng = fd.get("lng");
      const body = {
        name: fd.get("name").trim(), kind: fd.get("kind"), district_id: Number(fd.get("district_id")),
        address: fd.get("address").trim(), phone: fd.get("phone").trim() || null,
        open_time: fd.get("open_time"), close_time: fd.get("close_time"),
        paid_until: fd.get("paid_until") || null,
        photo_url: fd.get("photo_url").trim() || null,
        lat: lat ? Number(lat) : null, lng: lng ? Number(lng) : null,
      };
      try { await api("/api/admin/salons", { method: "POST", body: JSON.stringify(body) }); toast("Salon qo'shildi"); renderSalons(); }
      catch (err) { toast(err.message); }
    });

    const listEl = $("#salon-list");
    listEl.innerHTML = S.salons.map((s) => {
      const district = S.districts.find((d) => d.id === s.district_id);
      return `
      <div class="admin-card" data-salon="${s.id}">
        <div class="admin-card__head">
          <div>
            <div class="admin-card__title">${esc(s.name)}</div>
            <div class="admin-card__sub">${KIND_LABEL[s.kind] || s.kind}<span class="admin-dot-sep">·</span>${esc(district ? district.name : "")}<span class="admin-dot-sep">·</span>${esc(s.open_time)}–${esc(s.close_time)}</div>
            <div class="admin-card__sub">${esc(s.address)}${s.phone ? ` · ${esc(s.phone)}` : ""}</div>
          </div>
          ${switchHtml("active-" + s.id, !!s.is_active)}
        </div>
        <div class="admin-card__row">
          <span class="small muted">Obuna: ${s.paid_until ? esc(s.paid_until) : "yo'q"}</span>
          <input class="input" type="date" style="height:36px;width:150px" data-paid="${s.id}" value="${esc(s.paid_until || "")}">
        </div>
        <form class="admin-inline-form" data-photo="${s.id}">
          <input class="input" name="photo_url" type="url" placeholder="Rasm havolasi" value="${esc(s.photo_url || "")}">
          <button class="btn btn--small btn--quiet" type="submit">Saqlash</button>
        </form>
        <form class="admin-inline-form" data-loc="${s.id}">
          <input class="input" name="lat" type="number" step="0.000001" placeholder="lat" value="${esc(s.lat ?? "")}" style="max-width:120px">
          <input class="input" name="lng" type="number" step="0.000001" placeholder="lng" value="${esc(s.lng ?? "")}" style="max-width:120px">
          <button class="btn btn--small btn--quiet" type="submit">Koordinata saqlash</button>
        </form>
        <div class="admin-card__actions">
          <button class="admin-link-btn" data-action="go-masters" data-id="${s.id}" data-name="${esc(s.name)}">Ustalari →</button>
        </div>
      </div>`;
    }).join("");

    listEl.addEventListener("change", async (e) => {
      const sw = e.target.closest("[id^='active-']");
      if (sw) {
        const id = Number(sw.id.replace("active-", ""));
        try { await api("/api/admin/active", { method: "POST", body: JSON.stringify({ target: "salon", target_id: id, is_active: sw.checked }) }); toast("Saqlandi"); }
        catch (err) { toast(err.message); sw.checked = !sw.checked; }
        return;
      }
      const paid = e.target.closest("[data-paid]");
      if (paid) {
        const id = Number(paid.dataset.paid);
        try { await api("/api/admin/paid-until", { method: "POST", body: JSON.stringify({ target: "salon", target_id: id, paid_until: paid.value }) }); toast("Obuna yangilandi"); }
        catch (err) { toast(err.message); }
      }
    });

    listEl.addEventListener("submit", async (e) => {
      const photoForm = e.target.closest("[data-photo]");
      if (photoForm) {
        e.preventDefault();
        const id = Number(photoForm.dataset.photo);
        const url = new FormData(photoForm).get("photo_url").trim() || null;
        try { await api(`/api/admin/salons/${id}/photo`, { method: "POST", body: JSON.stringify({ photo_url: url }) }); toast("Rasm saqlandi"); }
        catch (err) { toast(err.message); }
        return;
      }
      const locForm = e.target.closest("[data-loc]");
      if (locForm) {
        e.preventDefault();
        const id = Number(locForm.dataset.loc);
        const fd = new FormData(locForm);
        const lat = fd.get("lat"), lng = fd.get("lng");
        try {
          await api(`/api/admin/salons/${id}/location`, {
            method: "POST",
            body: JSON.stringify({ lat: lat ? Number(lat) : null, lng: lng ? Number(lng) : null }),
          });
          toast("Koordinata saqlandi");
        } catch (err) { toast(err.message); }
      }
    });

    listEl.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-action='go-masters']");
      if (!btn) return;
      S.selectedSalonId = Number(btn.dataset.id);
      S.selectedSalonName = btn.dataset.name;
      S.tab = "masters";
      render();
    });
  }

  // ---------- 2. Ustalar ----------
  async function renderMasters() {
    shell(loadingCard());
    try {
      if (!S.salons.length) S.salons = await api("/api/admin/salons");
    } catch (e) { shell(`<div class="admin-card admin-error">${esc(e.message)}</div>`); return; }

    if (!S.salons.length) { shell(`<div class="admin-card admin-empty">Avval "Salonlar" bo'limida salon qo'shing.</div>`); return; }
    if (!S.selectedSalonId) S.selectedSalonId = S.salons[0].id;

    shell(`
      <div class="admin-card">
        <label><span class="small muted">Salon</span>
          <select class="select" id="salon-pick" style="margin-top:6px">
            ${S.salons.map((s) => `<option value="${s.id}" ${s.id === S.selectedSalonId ? "selected" : ""}>${esc(s.name)}</option>`).join("")}
          </select>
        </label>
        <form class="admin-form admin-form--2col" id="f-master" style="margin-top:14px">
          <div><label>Usta ismi</label><input class="input" name="name" required></div>
          <div><label>Obuna muddati (ixtiyoriy)</label><input class="input" name="paid_until" type="date"></div>
          <div class="span2"><label>Rasm havolasi (ixtiyoriy)</label><input class="input" name="photo_url" type="url" placeholder="https://..."></div>
          <div class="span2"><button class="btn" type="submit">Usta qo'shish</button></div>
        </form>
      </div>
      <div id="master-list">${loadingCard()}</div>
    `);

    $("#salon-pick").addEventListener("change", (e) => { S.selectedSalonId = Number(e.target.value); renderMasters(); });
    $("#f-master").addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      try {
        await api("/api/admin/masters", { method: "POST", body: JSON.stringify({
          salon_id: S.selectedSalonId, name: fd.get("name").trim(), paid_until: fd.get("paid_until") || null,
          photo_url: fd.get("photo_url").trim() || null,
        }) });
        toast("Usta qo'shildi"); renderMasters();
      } catch (err) { toast(err.message); }
    });

    let masters;
    try { masters = await api(`/api/admin/salons/${S.selectedSalonId}/masters`); }
    catch (e) { $("#master-list").innerHTML = `<div class="admin-error">${esc(e.message)}</div>`; return; }
    S.masters = masters;

    const listEl = $("#master-list");
    listEl.innerHTML = masters.length ? masters.map((m) => `
      <div class="admin-card">
        <div class="admin-card__head">
          <div>
            <div class="admin-card__title">${esc(m.name)}</div>
            <div class="admin-card__sub">${m.has_login ? `<span class="admin-chip admin-chip--ok">Login: ${esc(m.phone)}</span>` : `<span class="admin-chip admin-chip--off">Login yo'q</span>`}</div>
          </div>
          ${switchHtml("m-active-" + m.id, !!m.is_active)}
        </div>
        <div class="admin-card__row">
          <span class="small muted">Obuna: ${m.paid_until ? esc(m.paid_until) : "yo'q (salon obunasi ishlaydi)"}</span>
          <input class="input" type="date" style="height:36px;width:150px" data-paid="${m.id}" value="${esc(m.paid_until || "")}">
        </div>
        <form class="admin-inline-form" data-cred="${m.id}">
          <input class="input" name="phone" placeholder="Telefon (90 123 45 67)" value="${esc(m.phone || "")}" required>
          <input class="input" name="password" placeholder="${m.has_login ? "Yangi parol" : "Parol (4+)"}" type="text" required>
          <button class="btn btn--small btn--quiet" type="submit">${m.has_login ? "Parolni yangilash" : "Login berish"}</button>
        </form>
        <form class="admin-inline-form" data-mphoto="${m.id}">
          <input class="input" name="photo_url" type="url" placeholder="Rasm havolasi" value="${esc(m.photo_url || "")}">
          <button class="btn btn--small btn--quiet" type="submit">Saqlash</button>
        </form>
        <div class="admin-card__actions">
          <button class="admin-link-btn" data-action="go-services" data-id="${m.id}" data-name="${esc(m.name)}">Xizmatlari →</button>
        </div>
      </div>`).join("") : `<div class="admin-card admin-empty">Bu salonda hali usta yo'q</div>`;

    listEl.addEventListener("change", async (e) => {
      const sw = e.target.closest("[id^='m-active-']");
      if (sw) {
        const id = Number(sw.id.replace("m-active-", ""));
        try { await api("/api/admin/active", { method: "POST", body: JSON.stringify({ target: "master", target_id: id, is_active: sw.checked }) }); toast("Saqlandi"); }
        catch (err) { toast(err.message); sw.checked = !sw.checked; }
        return;
      }
      const paid = e.target.closest("[data-paid]");
      if (paid) {
        const id = Number(paid.dataset.paid);
        try { await api("/api/admin/paid-until", { method: "POST", body: JSON.stringify({ target: "master", target_id: id, paid_until: paid.value }) }); toast("Obuna yangilandi"); }
        catch (err) { toast(err.message); }
      }
    });

    listEl.addEventListener("submit", async (e) => {
      const form = e.target.closest("[data-cred]");
      if (form) {
        e.preventDefault();
        const id = Number(form.dataset.cred);
        const fd = new FormData(form);
        try {
          await api(`/api/admin/masters/${id}/credentials`, { method: "POST", body: JSON.stringify({ phone: fd.get("phone"), password: fd.get("password") }) });
          toast("Login saqlandi"); renderMasters();
        } catch (err) { toast(err.message); }
        return;
      }
      const photoForm = e.target.closest("[data-mphoto]");
      if (photoForm) {
        e.preventDefault();
        const id = Number(photoForm.dataset.mphoto);
        const url = new FormData(photoForm).get("photo_url").trim() || null;
        try { await api(`/api/admin/masters/${id}/photo`, { method: "POST", body: JSON.stringify({ photo_url: url }) }); toast("Rasm saqlandi"); }
        catch (err) { toast(err.message); }
      }
    });

    listEl.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-action='go-services']");
      if (!btn) return;
      S.selectedMasterId = Number(btn.dataset.id);
      S.selectedMasterName = btn.dataset.name;
      S.tab = "services";
      render();
    });
  }

  // ---------- 3. Xizmatlar ----------
  async function renderServices() {
    if (!S.selectedMasterId) {
      shell(`<div class="admin-card admin-empty">Avval "Ustalar" bo'limidan usta tanlang.</div>`);
      return;
    }
    shell(loadingCard());
    let services;
    try { services = await api(`/api/admin/masters/${S.selectedMasterId}/services`); }
    catch (e) { shell(`<div class="admin-card admin-error">${esc(e.message)}</div>`); return; }
    S.services = services;

    shell(`
      <div class="admin-card">
        <div class="admin-card__title">${esc(S.selectedMasterName || "Usta")} — xizmatlar</div>
        <form class="admin-form admin-form--2col" id="f-service" style="margin-top:10px">
          <div class="span2"><label>Xizmat nomi</label><input class="input" name="name" required></div>
          <div><label>Davomiyligi (daqiqa)</label><input class="input" name="duration_min" type="number" min="10" max="480" value="30" required></div>
          <div><label>Narxi (so'm)</label><input class="input" name="price" type="number" min="0" step="1000" required></div>
          <div class="span2"><button class="btn" type="submit">Xizmat qo'shish</button></div>
        </form>
      </div>
      <div id="service-list"></div>
    `);

    $("#f-service").addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      try {
        await api("/api/admin/services", { method: "POST", body: JSON.stringify({ master_id: S.selectedMasterId, name: fd.get("name").trim(), duration_min: Number(fd.get("duration_min")), price: Number(fd.get("price")) }) });
        toast("Xizmat qo'shildi"); renderServices();
      } catch (err) { toast(err.message); }
    });

    const listEl = $("#service-list");
    listEl.innerHTML = services.length ? services.map((sv) => `
      <div class="admin-card" data-svc="${sv.id}">
        <div class="admin-card__head">
          <form class="admin-form admin-form--2col" data-edit="${sv.id}" style="flex:1">
            <div class="span2"><input class="input" name="name" value="${esc(sv.name)}"></div>
            <div><input class="input" name="duration_min" type="number" value="${sv.duration_min}"></div>
            <div><input class="input" name="price" type="number" value="${sv.price}"></div>
          </form>
          ${switchHtml("sv-active-" + sv.id, !!sv.is_active)}
        </div>
        <div class="admin-card__actions">
          <button class="btn btn--small btn--quiet" data-action="save-svc" data-id="${sv.id}">Saqlash</button>
          <button class="btn btn--small btn--quiet btn--danger" data-action="del-svc" data-id="${sv.id}">O'chirish</button>
        </div>
      </div>`).join("") : `<div class="admin-card admin-empty">Hali xizmat yo'q</div>`;

    listEl.addEventListener("change", async (e) => {
      const sw = e.target.closest("[id^='sv-active-']");
      if (!sw) return;
      const id = Number(sw.id.replace("sv-active-", ""));
      try { await api(`/api/admin/services/${id}/active`, { method: "POST", body: JSON.stringify({ is_active: sw.checked }) }); toast("Saqlandi"); }
      catch (err) { toast(err.message); sw.checked = !sw.checked; }
    });

    listEl.addEventListener("click", async (e) => {
      const save = e.target.closest("[data-action='save-svc']");
      if (save) {
        const id = Number(save.dataset.id);
        const form = $(`[data-edit="${id}"]`);
        const fd = new FormData(form);
        try {
          await api(`/api/admin/services/${id}`, { method: "PATCH", body: JSON.stringify({ name: fd.get("name").trim(), duration_min: Number(fd.get("duration_min")), price: Number(fd.get("price")) }) });
          toast("Saqlandi"); renderServices();
        } catch (err) { toast(err.message); }
        return;
      }
      const del = e.target.closest("[data-action='del-svc']");
      if (del) {
        if (!confirm("Xizmatni butunlay o'chirishni tasdiqlaysizmi?")) return;
        const id = Number(del.dataset.id);
        try { await api(`/api/admin/services/${id}`, { method: "DELETE" }); toast("O'chirildi"); renderServices(); }
        catch (err) { toast(err.message); }
      }
    });
  }

  // ---------- 4. Bronlar ----------
  async function renderBookings() {
    try {
      if (!S.salons.length) S.salons = await api("/api/admin/salons");
    } catch (e) { shell(`<div class="admin-card admin-error">${esc(e.message)}</div>`); return; }

    shell(`
      <div class="admin-card">
        <div class="admin-inline-form">
          <div style="flex:1 1 160px"><label class="small muted">Sana</label><input class="input" id="b-date" type="date" value="${S.bookingDate}"></div>
          <div style="flex:1 1 220px"><label class="small muted">Salon</label>
            <select class="select" id="b-salon">
              <option value="">Barcha salonlar</option>
              ${S.salons.map((s) => `<option value="${s.id}" ${String(s.id) === String(S.bookingSalonId) ? "selected" : ""}>${esc(s.name)}</option>`).join("")}
            </select>
          </div>
        </div>
      </div>
      <div id="booking-list">${loadingCard()}</div>
    `);
    $("#b-date").addEventListener("change", (e) => { S.bookingDate = e.target.value; renderBookings(); });
    $("#b-salon").addEventListener("change", (e) => { S.bookingSalonId = e.target.value; renderBookings(); });

    let rows;
    try {
      const q = S.bookingSalonId ? `&salon_id=${S.bookingSalonId}` : "";
      rows = await api(`/api/admin/bookings?date=${S.bookingDate}${q}`);
    } catch (e) { $("#booking-list").innerHTML = `<div class="admin-card admin-error">${esc(e.message)}</div>`; return; }
    S.bookings = rows;

    const listEl = $("#booking-list");
    listEl.innerHTML = rows.length ? rows.map((b) => `
      <div class="admin-card">
        <div class="admin-card__head">
          <div>
            <div class="admin-card__title">${esc(b.start_at.slice(11))} — ${esc(b.client_name)}</div>
            <div class="admin-card__sub">${esc(b.salon_name)} · ${esc(b.master_name)} · ${esc(b.service_name)} · ${money(b.price)}</div>
            <div class="admin-card__sub">${esc(b.client_phone)}</div>
          </div>
          <span class="admin-chip ${b.status === "done" ? "admin-chip--ok" : b.status === "booked" ? "" : "admin-chip--off"}">${STATUS_LABEL[b.status] || b.status}</span>
        </div>
        ${b.status === "booked" ? `
        <div class="admin-card__actions">
          <button class="btn btn--small btn--quiet" data-action="st" data-no="${esc(b.booking_no)}" data-status="done">Bajarildi</button>
          <button class="btn btn--small btn--quiet" data-action="st" data-no="${esc(b.booking_no)}" data-status="no_show">Kelmadi</button>
          <button class="btn btn--small btn--quiet btn--danger" data-action="st" data-no="${esc(b.booking_no)}" data-status="cancelled">Bekor qilish</button>
        </div>` : ""}
      </div>`).join("") : `<div class="admin-card admin-empty">Bu sanada bron yo'q</div>`;

    listEl.addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-action='st']");
      if (!btn) return;
      try { await api(`/api/admin/bookings/${btn.dataset.no}/status`, { method: "POST", body: JSON.stringify({ status: btn.dataset.status }) }); toast("Yangilandi"); renderBookings(); }
      catch (err) { toast(err.message); }
    });
  }

  // ---------- umumiy navigatsiya ----------
  function render() {
    if (!S.token) { renderLogin(); return; }
    const fn = { salons: renderSalons, masters: renderMasters, services: renderServices, bookings: renderBookings }[S.tab];
    fn();
  }

  document.addEventListener("click", (e) => {
    const tabBtn = e.target.closest("#admin-tabs [data-tab]");
    if (tabBtn) { S.tab = tabBtn.dataset.tab; render(); return; }
    const out = e.target.closest("[data-action='logout']");
    if (out) {
      localStorage.removeItem(TOKEN_KEY);
      S.token = "";
      render();
    }
  });

  function boot() { render(); }
  boot();
})();
