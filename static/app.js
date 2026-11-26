/* BandQil mijoz ilovasi: Telegram Mini App ichida ham, oddiy brauzerda ham ishlaydi. */
(() => {
  "use strict";

  // ---------- yordamchilar ----------
  const $ = (sel, root = document) => root.querySelector(sel);
  const app = $("#app");
  const WEEK = ["Yak", "Dush", "Sesh", "Chor", "Pay", "Jum", "Shan"];
  const WEEK_FULL = ["Yakshanba", "Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba"];
  const MONTHS = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"];
  const STATUS = { booked: "Band qilingan", done: "Bajarildi", cancelled: "Bekor qilindi", no_show: "Kelmadi", past: "Vaqti o'tgan" };

  // Flat ikonkalar (emoji o'rniga) — har bir yo'nalish uchun
  const ICON_BARBER = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><line x1="20" y1="4" x2="8.5" y2="15.5"/><line x1="8.5" y1="8.5" x2="20" y2="20"/></svg>`;
  const ICON_BEAUTY = `<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2c.6 3.2 1.9 5.6 4.3 7.7C18.8 11.8 21 12.6 22 13c-1 .4-3.2 1.2-5.7 3.3-2.4 2.1-3.7 4.5-4.3 7.7-.6-3.2-1.9-5.6-4.3-7.7C5.2 14.2 3 13.4 2 13c1-.4 3.2-1.2 5.7-3.3C10.1 7.6 11.4 5.2 12 2Z"/></svg>`;
  const ICON_COMPUTER = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/></svg>`;
  const ICON_BILLIARD = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="15" cy="9" r="4.2"/><circle cx="15" cy="9" r="1" fill="currentColor" stroke="none"/><line x1="2.5" y1="21.5" x2="9.8" y2="14.2"/></svg>`;

  // BandQil logotip belgisi (bosh sahifa uchun) — navy kvadrat + oltin "bron" aksenti
  const LOGO_MARK = `<svg width="48" height="48" viewBox="0 0 48 48" aria-hidden="true">
    <rect x="1.5" y="1.5" width="45" height="45" rx="13" fill="#15171C" stroke="#F6C945" stroke-width="2.5"/>
    <text x="16.5" y="32.5" font-family="'Bricolage Grotesque', sans-serif" font-weight="800" font-size="24" fill="#fff">B</text>
    <circle cx="34.5" cy="33.5" r="9.5" fill="#F6C945"/>
    <rect x="29.8" y="29.2" width="9.4" height="8.4" rx="1.8" fill="none" stroke="#15171C" stroke-width="1.5"/>
    <line x1="29.8" y1="31.9" x2="39.2" y2="31.9" stroke="#15171C" stroke-width="1.5"/>
  </svg>`;

  // To'rtta yo'nalish: har biri o'z mavzusi (rang palitrasi) va resurs nomi (usta/stol/kompyuter) bilan
  const KIND_META = {
    barbershop: { theme: "barber", label: "Barbershoplar", shortLabel: "Barbershop", icon: ICON_BARBER, desc: "Soch va soqol olish, erkaklar parvarishi", resource: "Usta", resourcePl: "usta" },
    beauty: { theme: "beauty", label: "Go'zallik salonlari", shortLabel: "Go'zallik saloni", icon: ICON_BEAUTY, desc: "Soch turmagi, manikyur, kosmetologiya", resource: "Usta", resourcePl: "usta" },
    computer_club: { theme: "club", label: "Kompyuter klublari", shortLabel: "Kompyuter klubi", icon: ICON_COMPUTER, desc: "Zamonaviy o'yin va internet klublar", resource: "Kompyuter", resourcePl: "kompyuter" },
    billiard_club: { theme: "billiard", label: "Billyard klublari", shortLabel: "Billyard klubi", icon: ICON_BILLIARD, desc: "Do'stlar bilan maroqli dam olish", resource: "Stol", resourcePl: "stol" },
  };
  const themeFor = (kind) => (KIND_META[kind] && KIND_META[kind].theme) || "neutral";
  const setTheme = (t) => { document.body.dataset.theme = t; };

  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = (n) => Number(n).toLocaleString("ru-RU") + " so'm";
  const durLabel = (min) => {
    if (min < 60) return `${min} daqiqa`;
    const h = Math.floor(min / 60), rest = min % 60;
    return rest ? `${h} soat ${rest} daqiqa` : `${h} soat`;
  };
  const distanceLabel = (km) => km == null ? "" : (km < 1 ? `${Math.max(1, Math.round(km * 1000))} m` : `${km.toFixed(1)} km`);
  const pad = (n) => String(n).padStart(2, "0");
  const ymd = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const parseDT = (s) => new Date(s.replace(" ", "T"));
  const dayLabel = (d) => `${WEEK_FULL[d.getDay()]}, ${d.getDate()}-${MONTHS[d.getMonth()]}`;

  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (_) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (_) { /* brauzer ruxsat bermasa, e'tiborsiz */ } },
  };

  // ---------- Telegram ----------
  const tg = window.Telegram && window.Telegram.WebApp;
  if (tg) { try { tg.ready(); tg.expand(); } catch (_) { /* e'tiborsiz */ } }

  function clientId() {
    const tgUser = tg && tg.initDataUnsafe && tg.initDataUnsafe.user;
    if (tgUser && tgUser.id) return tgUser.id;
    let id = parseInt(store.get("bq_uid"), 10);
    if (!id) { id = 100000000 + Math.floor(Math.random() * 899999999); store.set("bq_uid", String(id)); }
    return id;
  }
  const CLIENT_ID = clientId();

  // ---------- mijozning joylashuvi (masofani ko'rsatish uchun, ixtiyoriy) ----------
  // Ruxsat so'rab o'tirib ro'yxat yuklanishini to'xtatib qo'ymaymiz: avval joylashuvsiz ko'rsatamiz,
  // keyin (agar ruxsat berilsa) masofa bilan qayta yuklaymiz.
  let geoCoords = null;
  let geoRequested = false;
  function requestGeo(onReady) {
    if (geoCoords) { onReady(); return; }
    if (geoRequested || !(navigator.geolocation)) return;
    geoRequested = true;
    navigator.geolocation.getCurrentPosition(
      (pos) => { geoCoords = { lat: pos.coords.latitude, lng: pos.coords.longitude }; onReady(); },
      () => { /* ruxsat berilmadi yoki xato — joylashuvsiz davom etamiz */ },
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 300000 }
    );
  }

  // ---------- server bilan aloqa ----------
  async function api(path, options = {}) {
    let res;
    const headers = {};
    if (options.body) headers["Content-Type"] = "application/json";
    // Telegram ichida ochilgan bo'lsa, serverga haqiqiy foydalanuvchini tasdiqlash uchun
    // Telegram imzolagan initData'ni ham yuboramiz (server buni tekshiradi, soxtalashtirib bo'lmaydi).
    if (tg && tg.initData) headers["X-Telegram-Init-Data"] = tg.initData;
    try {
      res = await fetch(path, {
        method: options.method || "GET",
        headers: Object.keys(headers).length ? headers : undefined,
        body: options.body ? JSON.stringify(options.body) : undefined,
      });
    } catch (_) {
      throw { code: "network", message: "Internet yoki server bilan aloqa yo'q. Qayta urinib ko'ring." };
    }
    let data = null;
    try { data = await res.json(); } catch (_) { /* bo'sh javob */ }
    if (!res.ok) {
      const message = data && typeof data.detail === "string" ? data.detail : "Ma'lumotlarni tekshirib, qayta urinib ko'ring.";
      throw { code: (data && data.code) || "error", message };
    }
    return data;
  }

  let toastTimer;
  function toast(text) {
    const el = $("#toast");
    el.textContent = text;
    el.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove("show"), 3200);
  }

  // ---------- holat va yo'naltirish ----------
  const S = {
    stack: [],                       // orqaga qaytish uchun
    view: { name: "home" },
    districtId: parseInt(store.get("bq_district"), 10) || null,
    kind: "",
    name: store.get("bq_name") || "",
    phone: store.get("bq_phone") || "",
    book: null,                      // {salon, master, service, date, time, slots, showNearby}
    token: 0,                        // eski javoblarni bekor qilish uchun
  };

  function go(view, { replace = false } = {}) {
    if (!replace) S.stack.push(S.view);
    S.view = view;
    S.token++;
    render();
    window.scrollTo(0, 0);
  }
  function back() {
    S.view = S.stack.pop() || { name: "home" };
    S.token++;
    render();
  }
  function root(name) {
    S.stack = [];
    S.view = { name };
    S.token++;
    render();
    window.scrollTo(0, 0);
  }

  function setTabs(active) {
    document.body.dataset.tabs = active ? "on" : "off";
    document.querySelectorAll("#tabs button").forEach((b) => {
      if (b.dataset.root === active) b.setAttribute("aria-current", "page");
      else b.removeAttribute("aria-current");
    });
  }

  function render() {
    const v = S.view.name;
    const fn = { home: renderHome, list: renderList, salon: renderSalon, book: renderBook, done: renderDone, mine: renderMine }[v];
    // Pastki panel faqat bosh sahifa (yo'nalish/ro'yxat) va "Bronlarim"da ko'rinadi
    setTabs(v === "home" || v === "list" ? "home" : v === "mine" ? "mine" : null);
    fn();
  }

  const loading = () => `<p class="loading">Yuklanmoqda…</p>`;
  const errorBox = (e, retry) => `<div class="empty"><h2>Yuklab bo'lmadi</h2><p class="muted">${esc(e.message)}</p><button class="btn btn--quiet btn--small" data-action="${retry}">Qayta urinish</button></div>`;
  const backBtn = (label = "Orqaga") => `<button class="back" data-action="back"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m15 5-7 7 7 7"/></svg>${esc(label)}</button>`;

  function scoreBlock(rating, count) {
    if (rating == null) return `<span class="score score--new">Yangi</span>`;
    return `<span class="score">${Number(rating).toFixed(1)}<small>${count} baho</small></span>`;
  }
  const STAR_SM = `<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="m12 2.8 2.9 6 6.6.9-4.8 4.6 1.2 6.5L12 17.6l-5.9 3.2 1.2-6.5L2.5 9.7l6.6-.9z"/></svg>`;
  function ratingLine(rating, count) {
    if (rating == null) return `<span class="rating rating--new">Yangi</span>`;
    return `<span class="rating"><span class="rating__star">${STAR_SM}</span>${Number(rating).toFixed(1)} <span class="rating__count">(${count})</span></span>`;
  }

  // ---------- 1. Bosh sahifa: yo'nalish tanlash ----------
  function renderHome() {
    setTheme("neutral");
    app.innerHTML = `
      <div class="brand-mark">
        <span class="brand-mark__badge">${LOGO_MARK}</span>
        <span class="brand-mark__word">BandQil</span>
      </div>
      <nav class="brand-nav" aria-label="Yo'nalish">
        ${Object.entries(KIND_META).map(([k, m]) => `<button type="button" data-action="choose-kind" data-kind="${k}">${esc(m.label)}</button>`).join("")}
      </nav>
      <h1 class="home-title">BandQil ilovasiga xush kelibsiz</h1>
      <p class="muted hero-sub">BandQil'da vaqtingizni va pulingizni tejang.</p>
      <div class="directions">
        ${Object.entries(KIND_META).map(([k, m]) => `
          <button class="direction-card direction-card--${m.theme}" data-action="choose-kind" data-kind="${k}">
            <span class="direction-card__icon" aria-hidden="true">${m.icon}</span>
            <span class="direction-card__body">
              <span class="direction-card__kicker">Yo'nalish</span>
              <span class="direction-card__title">${esc(m.label)}</span>
              <span class="direction-card__desc">${esc(m.desc)}</span>
            </span>
            <span class="direction-card__arrow" aria-hidden="true">›</span>
          </button>`).join("")}
      </div>`;
  }

  // ---------- 1b. Tuman va salonlar ro'yxati (tanlangan yo'nalish bo'yicha) ----------
  async function renderList() {
    setTheme(themeFor(S.kind));
    const my = S.token;
    const meta = KIND_META[S.kind] || { label: "Hamma salonlar", icon: ICON_BEAUTY };
    app.innerHTML = `<header class="top">${backBtn("Yo'nalish")}</header>
      <div class="head">
        <span class="kind-tag">${meta.icon} ${esc(meta.label)}</span>
        <h1>${esc(meta.label)}</h1>
      </div>
      <div class="theme-pills" id="kinds" role="group" aria-label="Yo'nalish">
        ${Object.entries(KIND_META).map(([k, m]) => `<button data-kind="${k}" aria-pressed="${S.kind === k}">${m.icon} ${esc(m.label)}</button>`).join("")}
      </div>
      <div id="list-body">${loading()}</div>`;
    let districts;
    try { districts = await api("/api/districts"); }
    catch (e) { if (my === S.token) $("#list-body").innerHTML = errorBox(e, "retry"); return; }
    if (my !== S.token) return;

    if (!districts.length) {
      $("#list-body").innerHTML = `<div class="empty"><h2>Salonlar hali qo'shilmagan</h2><p class="muted">Tez orada shu yerda salonlar paydo bo'ladi.</p></div>`;
      return;
    }
    if (!districts.some((d) => d.id === S.districtId)) S.districtId = districts[0].id;

    $("#list-body").innerHTML = `
      <label class="field"><span>Tuman</span>
        <select class="select" id="district">${districts.map((d) => `<option value="${d.id}" ${d.id === S.districtId ? "selected" : ""}>${esc(d.name)}</option>`).join("")}</select>
      </label>
      <div id="salons">${loading()}</div>`;
    loadSalons();
    requestGeo(() => { if (S.view.name === "list") loadSalons(); });
  }

  async function loadSalons() {
    const my = S.token;
    const box = $("#salons");
    if (!box) return;
    const q = new URLSearchParams({ district_id: S.districtId });
    if (S.kind) q.set("kind", S.kind);
    if (geoCoords) { q.set("lat", geoCoords.lat); q.set("lng", geoCoords.lng); }
    let salons;
    try { salons = await api("/api/salons?" + q); }
    catch (e) { if (my === S.token) box.innerHTML = errorBox(e, "retry-salons"); return; }
    if (my !== S.token) return;
    if (!salons.length) {
      box.innerHTML = `<div class="empty"><h2>Bu tumanda salon topilmadi</h2><p class="muted">Boshqa tumanni yoki turini tanlab ko'ring.</p></div>`;
      return;
    }
    S.salons = salons;
    box.innerHTML = salons.map((s, i) => {
      const meta = KIND_META[s.kind] || KIND_META.barbershop;
      return `
      <button class="salon-card" data-action="open-salon" data-i="${i}">
        <span class="salon-card__media" aria-hidden="true">${s.photo_url ? `<img src="${esc(s.photo_url)}" alt="" loading="lazy">` : meta.icon}</span>
        <span class="salon-card__body">
          <span class="salon-card__head"><span class="salon-card__name">${esc(s.name)}</span><span class="salon-card__chevron" aria-hidden="true">›</span></span>
          <span class="salon-card__stats">${ratingLine(s.rating, s.reviews_count)}<span class="dot" aria-hidden="true">·</span>${esc(s.open_time)}–${esc(s.close_time)}${s.distance_km != null ? `<span class="dot" aria-hidden="true">·</span><span class="salon-card__dist">${distanceLabel(s.distance_km)}</span>` : ""}</span>
          <span class="salon-card__addr">${esc(s.address)}</span>
          <span class="salon-card__meta">${esc(meta.shortLabel)}</span>
        </span>
      </button>`;
    }).join("");
  }

  // ---------- 2. Salon: ustalar va xizmatlar ----------
  async function renderSalon() {
    const my = S.token;
    const salon = S.view.salon;
    setTheme(themeFor(salon.kind));
    const meta = KIND_META[salon.kind] || KIND_META.barbershop;
    app.innerHTML = `<header class="top">${backBtn("Salonlar")}</header>
      <div class="head">${meta ? `<span class="kind-tag">${meta.icon} ${esc(meta.label)}</span>` : ""}<h1>${esc(salon.name)}</h1>
      <p class="muted">${esc(salon.address)}</p>${salon.phone ? `<p class="small muted">Tel: ${esc(salon.phone)}</p>` : ""}</div>
      <div id="masters">${loading()}</div>`;
    let masters;
    try { masters = await api(`/api/salons/${salon.id}/masters`); }
    catch (e) { if (my === S.token) $("#masters").innerHTML = errorBox(e, "retry"); return; }
    if (my !== S.token) return;
    masters = masters.filter((m) => m.services.length);
    S.masters = masters;
    if (!masters.length) {
      $("#masters").innerHTML = `<div class="empty"><h2>Hozircha ${esc(meta.resourcePl)} yo'q</h2><p class="muted">Bu salonda navbat olish yopiq. Boshqa salonni tanlang.</p></div>`;
      return;
    }
    $("#masters").innerHTML = masters.map((m, mi) => `
      <section class="master">
        <div class="master__head">
          <span class="master__avatar" aria-hidden="true">${m.photo_url ? `<img src="${esc(m.photo_url)}" alt="" loading="lazy">` : esc((m.name || "?").slice(0, 1).toUpperCase())}</span>
          <h2 class="master__name">${esc(m.name)}</h2>
          ${scoreBlock(m.rating, m.reviews_count)}
        </div>
        ${m.services.map((sv, si) => `
          <button class="service" data-action="pick-service" data-m="${mi}" data-s="${si}">
            <span><span class="service__name">${esc(sv.name)}</span><span class="service__dur">${durLabel(sv.duration_min)}</span></span>
            <span class="price">${money(sv.price)}</span>
          </button>`).join("")}
      </section>`).join("");
  }

  // ---------- 3. Sana, vaqt va bron ----------
  function startBooking(salon, master, service, date, time) {
    S.book = { salon, master, service, date: date || ymd(new Date()), time: time || null, slots: null, showNearby: false };
    go({ name: "book" });
  }

  function renderBook() {
    const b = S.book;
    setTheme(themeFor(b.salon.kind));
    const days = Array.from({ length: 14 }, (_, i) => { const d = new Date(); d.setDate(d.getDate() + i); return d; });
    app.innerHTML = `<header class="top">${backBtn(b.salon.name)}</header>
      <div class="head"><h1>${esc(b.service.name)}</h1>
        <p>${esc(b.master.name)}, ${esc(b.salon.name)}</p>
        <p class="muted small">${esc(b.salon.address)}<br>${durLabel(b.service.duration_min)} · ${money(b.service.price)}</p></div>
      <div class="dates" id="dates" role="group" aria-label="Sana">${days.map((d) => `
        <button class="date" data-action="pick-date" data-date="${ymd(d)}" aria-pressed="${ymd(d) === b.date}"><span>${WEEK[d.getDay()]}</span><b>${d.getDate()}</b><span>${MONTHS[d.getMonth()].slice(0, 3)}</span></button>`).join("")}</div>
      <div id="slots-box">${loading()}</div>
      <div id="nearby-box"></div>
      <div class="bar"><div class="bar__sum" id="sum"></div><button class="btn" id="confirm" data-action="confirm" disabled>Band qilish</button></div>`;
    const sel = $(`.date[aria-pressed="true"]`);
    if (sel) sel.scrollIntoView({ inline: "center", block: "nearest" });
    loadSlots();
  }

  function updateSum() {
    const b = S.book;
    const sum = $("#sum"), btn = $("#confirm");
    if (!sum || !btn) return;
    const d = new Date(b.date + "T00:00");
    sum.innerHTML = b.time ? `<b>${dayLabel(d)}, ${esc(b.time)}</b> · ${money(b.service.price)}` : "Vaqtni tanlang";
    btn.disabled = !b.time;
  }

  async function loadSlots() {
    const my = S.token;
    const b = S.book;
    const box = $("#slots-box");
    if (!box) return;
    box.innerHTML = loading();
    $("#nearby-box").innerHTML = "";
    let data;
    try { data = await api(`/api/masters/${b.master.id}/slots?service_id=${b.service.id}&date=${b.date}`); }
    catch (e) { if (my === S.token) box.innerHTML = errorBox(e, "retry-slots"); return; }
    if (my !== S.token) return;
    b.slots = data.slots;
    if (b.time && !b.slots.includes(b.time)) b.time = null;
    drawSlots();
    updateSum();
    if (!b.slots.length) { b.showNearby = true; }
    if (b.showNearby) loadNearby(); else drawNearbyLink();
  }

  function drawSlots() {
    const b = S.book;
    const box = $("#slots-box");
    if (!b.slots.length) {
      box.innerHTML = `<div class="empty"><h2>Bu kunda bo'sh vaqt yo'q</h2><p class="muted">${esc(b.master.name)} bu kuni band. Boshqa kunni tanlang yoki quyidagi yaqin salonlarni ko'ring.</p></div>`;
      return;
    }
    box.innerHTML = `<h2 class="block-title">Bo'sh vaqtlar</h2>
      <div class="slots" role="group" aria-label="Vaqt">${b.slots.map((t) => `<button class="slot" data-action="pick-time" data-time="${t}" aria-pressed="${t === b.time}">${t}</button>`).join("")}</div>
      <h2 class="block-title">Ma'lumotlaringiz</h2>
      <label class="field" style="margin-top:0"><span>Ism</span><input class="input" id="name" autocomplete="name" maxlength="60" value="${esc(S.name)}"></label>
      <label class="field"><span>Telefon</span><input class="input" id="phone" type="tel" inputmode="tel" autocomplete="tel" maxlength="20" placeholder="+998 90 123 45 67" value="${esc(S.phone)}"></label>`;
  }

  function drawNearbyLink() {
    $("#nearby-box").innerHTML = `<p class="note"><button class="link" data-action="show-nearby">Boshqa salonlarda bo'sh vaqtni ko'rish</button></p>`;
  }

  async function loadNearby() {
    const my = S.token;
    const b = S.book;
    const box = $("#nearby-box");
    box.innerHTML = `<h2 class="section-title">Yaqin atrofda bo'sh joylar</h2>${loading()}`;
    const q = new URLSearchParams({ district_id: b.salon.district_id, date: b.date, duration_min: b.service.duration_min, exclude_master_id: b.master.id });
    if (b.salon.kind) q.set("kind", b.salon.kind);
    if (geoCoords) { q.set("lat", geoCoords.lat); q.set("lng", geoCoords.lng); }
    let items;
    try { items = await api("/api/nearby?" + q); }
    catch (e) { if (my === S.token) box.innerHTML = errorBox(e, "retry-nearby"); return; }
    if (my !== S.token) return;
    b.near = items;
    if (!items.length) {
      box.innerHTML = `<h2 class="section-title">Yaqin atrofda bo'sh joylar</h2><p class="muted note">Bu kuni shu tumanda bo'sh vaqt topilmadi. Boshqa kunni tanlab ko'ring.</p>`;
      return;
    }
    box.innerHTML = `<h2 class="section-title">Yaqin atrofda bo'sh joylar</h2><p class="muted small">Vaqtni bossangiz, shu ustaga o'tasiz.</p>` +
      items.map((it, i) => `
        <section class="master">
          <div class="master__head">
            ${it.master_photo_url ? `<span class="master__avatar" aria-hidden="true"><img src="${esc(it.master_photo_url)}" alt="" loading="lazy"></span>` : ""}
            <div><h3>${esc(it.master_name)}, ${esc(it.salon_name)}</h3><p class="small muted">${esc(it.address)}${it.distance_km != null ? ` · ${distanceLabel(it.distance_km)}` : ""}</p></div>
            ${scoreBlock(it.rating, it.reviews_count)}
          </div>
          <div class="slots slots--small">${it.slots.map((t) => `<button class="slot" data-action="pick-near" data-i="${i}" data-time="${t}">${t}</button>`).join("")}</div>
        </section>`).join("");
    requestGeo(() => { if (S.view.name === "book" && S.book === b) loadNearby(); });
  }

  async function confirmBooking() {
    const b = S.book;
    const name = ($("#name") || {}).value || "";
    const phone = ($("#phone") || {}).value || "";
    if (name.trim().length < 2) { toast("Ismingizni kiriting"); $("#name") && $("#name").focus(); return; }
    if (phone.replace(/\D/g, "").length < 9) { toast("Telefon raqamini to'liq kiriting"); $("#phone") && $("#phone").focus(); return; }
    const btn = $("#confirm");
    btn.disabled = true;
    btn.textContent = "Band qilinmoqda…";
    try {
      const booking = await api("/api/bookings", {
        method: "POST",
        body: { master_id: b.master.id, service_id: b.service.id, date: b.date, time: b.time, client_name: name.trim(), client_phone: phone.trim(), client_tg_id: CLIENT_ID },
      });
      S.name = name.trim(); S.phone = phone.trim();
      store.set("bq_name", S.name); store.set("bq_phone", S.phone);
      S.stack = [];
      S.view = { name: "done", booking, kind: b.salon.kind };
      S.token++;
      render();
      window.scrollTo(0, 0);
    } catch (e) {
      toast(e.message);
      btn.textContent = "Band qilish";
      if (e.code === "slot_taken") { b.time = null; loadSlots(); } else { btn.disabled = false; }
    }
  }

  // ---------- talon (bron hujjati) ----------
  function talon(bk, { stamp = false, actions = "" } = {}) {
    const start = parseDT(bk.start_at);
    const past = bk.status !== "booked" || start <= new Date();
    const label = bk.status === "booked" && start <= new Date() ? STATUS.past : STATUS[bk.status];
    return `<article class="talon ${past ? "talon--past" : ""}">
      ${stamp ? `<span class="stamp" aria-hidden="true">BAND</span>` : ""}
      <div class="talon__when">${dayLabel(start)}</div>
      <div class="talon__time">${bk.start_at.slice(11)}–${bk.end_at.slice(11)}</div>
      <dl>
        <div class="talon__row"><dt>${esc((KIND_META[bk.kind] || KIND_META.barbershop).resource)}</dt><dd>${esc(bk.master_name)}, ${esc(bk.salon_name)}</dd></div>
        <div class="talon__row"><dt>Manzil</dt><dd>${esc(bk.address)}</dd></div>
        <div class="talon__row"><dt>Xizmat</dt><dd>${esc(bk.service_name)}, ${money(bk.price)}</dd></div>
      </dl>
      <div class="talon__cut"></div>
      <div class="talon__foot"><span class="talon__no">${esc(bk.booking_no)}</span><span class="status status--${bk.status}">${esc(label)}</span></div>
      ${actions}
    </article>`;
  }

  function renderDone() {
    setTheme(themeFor(S.view.kind));
    const bk = S.view.booking;
    app.innerHTML = `<header class="top"><span class="brand">BandQil</span></header>
      <h1>Navbat band qilindi</h1>
      <p class="muted" style="margin-top:8px">Bron raqamini salonda ayting.</p>
      ${talon(bk, { stamp: true })}
      <button class="btn" data-action="to-mine">Bronlarim</button>
      <button class="btn btn--quiet" style="margin-top:10px" data-action="to-home">Bosh sahifa</button>`;
  }

  // ---------- 4. Bronlarim ----------
  async function renderMine() {
    setTheme("neutral");
    const my = S.token;
    app.innerHTML = `<header class="top"><span class="brand">BandQil</span></header><h1>Bronlarim</h1><div id="mine-body">${loading()}</div>`;
    let list;
    try { list = await api("/api/my-bookings?client_tg_id=" + CLIENT_ID); }
    catch (e) { if (my === S.token) $("#mine-body").innerHTML = errorBox(e, "retry"); return; }
    if (my !== S.token) return;
    S.mine = list;
    if (!list.length) {
      $("#mine-body").innerHTML = `<div class="empty"><h2>Hali bron yo'q</h2><p class="muted">Salon tanlab, birinchi navbatingizni band qiling.</p><button class="btn btn--small" data-action="to-home">Salonlarni ko'rish</button></div>`;
      return;
    }
    const now = new Date();
    const upcoming = list.filter((b) => b.status === "booked" && parseDT(b.start_at) > now).reverse();
    const rest = list.filter((b) => !upcoming.includes(b));
    const cardActions = (b) => {
      if (upcoming.includes(b)) return `<div class="talon__actions"><button class="btn btn--quiet btn--small btn--danger" data-action="cancel" data-no="${esc(b.booking_no)}">Bekor qilish</button></div>`;
      if (b.status === "done" && !b.reviewed) return `<div class="talon__actions"><button class="btn btn--small" data-action="review" data-no="${esc(b.booking_no)}">Baho berish</button></div>`;
      return "";
    };
    $("#mine-body").innerHTML =
      (upcoming.length ? `<h2 class="section-title">Kelgusi navbatlar</h2>${upcoming.map((b) => talon(b, { actions: cardActions(b) })).join("")}` : "") +
      (rest.length ? `<h2 class="section-title">Oldingilari</h2>${rest.map((b) => talon(b, { actions: cardActions(b) })).join("")}` : "");
  }

  // ---------- varaqlar: bekor qilish va baho ----------
  function openSheet(html) {
    closeSheet();
    const el = document.createElement("div");
    el.className = "sheet";
    el.id = "sheet";
    el.innerHTML = `<div class="sheet__panel" role="dialog" aria-modal="true">${html}</div>`;
    el.addEventListener("click", (e) => { if (e.target === el || e.target.closest("[data-close]")) closeSheet(); });
    document.body.appendChild(el);
    const first = el.querySelector("button");
    if (first) first.focus();
    return el;
  }
  function closeSheet() { const el = $("#sheet"); if (el) el.remove(); }

  function cancelSheet(no) {
    const el = openSheet(`<h2>Bronni bekor qilamizmi?</h2><p class="muted">${esc(no)} raqamli navbat bekor qilinadi, vaqt boshqalarga ochiladi.</p>
      <button class="btn btn--danger-fill" id="do-cancel" style="background:var(--pole)">Ha, bekor qilish</button>
      <button class="btn btn--quiet" data-close>Qolsin</button>`);
    $("#do-cancel", el).addEventListener("click", async (ev) => {
      ev.target.disabled = true;
      try {
        await api(`/api/bookings/${encodeURIComponent(no)}/cancel`, { method: "POST", body: { client_tg_id: CLIENT_ID } });
        closeSheet();
        toast("Bron bekor qilindi");
        renderMine();
      } catch (e) { ev.target.disabled = false; toast(e.message); }
    });
  }

  const STAR = `<svg width="38" height="38" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="m12 2.8 2.9 6 6.6.9-4.8 4.6 1.2 6.5L12 17.6l-5.9 3.2 1.2-6.5L2.5 9.7l6.6-.9z"/></svg>`;
  function reviewSheet(no) {
    let rating = 0;
    const el = openSheet(`<h2>Xizmatni baholang</h2><p class="muted">Bahoyingiz boshqa mijozlarga tanlashda yordam beradi.</p>
      <div class="stars" role="group" aria-label="Baho">${[1, 2, 3, 4, 5].map((n) => `<button class="star" data-n="${n}" aria-pressed="false" aria-label="${n} yulduz">${STAR}</button>`).join("")}</div>
      <textarea class="textarea" id="comment" maxlength="500" placeholder="Izoh (ixtiyoriy)"></textarea>
      <button class="btn" id="send-review" disabled>Yuborish</button>
      <button class="btn btn--quiet" data-close>Keyinroq</button>`);
    const send = $("#send-review", el);
    el.querySelectorAll(".star").forEach((s) => s.addEventListener("click", () => {
      rating = Number(s.dataset.n);
      el.querySelectorAll(".star").forEach((x) => x.setAttribute("aria-pressed", String(Number(x.dataset.n) <= rating)));
      send.disabled = false;
    }));
    send.addEventListener("click", async () => {
      send.disabled = true;
      try {
        await api("/api/reviews", { method: "POST", body: { booking_no: no, client_tg_id: CLIENT_ID, rating, comment: $("#comment", el).value } });
        closeSheet();
        toast("Rahmat! Bahoyingiz qabul qilindi");
        renderMine();
      } catch (e) { send.disabled = false; toast(e.message); }
    });
  }

  // ---------- hodisalar (bitta joyda) ----------
  document.addEventListener("click", (e) => {
    const tab = e.target.closest("#tabs [data-root]");
    if (tab) { root(tab.dataset.root); return; }
    const kind = e.target.closest("#kinds [data-kind]");
    if (kind) {
      S.kind = kind.dataset.kind;
      document.querySelectorAll("#kinds button").forEach((x) => x.setAttribute("aria-pressed", String(x === kind)));
      setTheme(themeFor(S.kind));
      const meta = KIND_META[S.kind];
      if (meta) {
        const tag = $(".kind-tag"); if (tag) tag.innerHTML = `${meta.icon} ${esc(meta.label)}`;
        const h1 = $(".head h1"); if (h1) h1.textContent = meta.label;
      }
      loadSalons();
      return;
    }
    const el = e.target.closest("[data-action]");
    if (!el) return;
    const b = S.book;
    switch (el.dataset.action) {
      case "back": back(); break;
      case "retry": render(); break;
      case "retry-salons": loadSalons(); break;
      case "retry-slots": loadSlots(); break;
      case "retry-nearby": loadNearby(); break;
      case "to-home": root("home"); break;
      case "to-mine": root("mine"); break;
      case "choose-kind": S.kind = el.dataset.kind; go({ name: "list" }); break;
      case "open-salon": go({ name: "salon", salon: S.salons[Number(el.dataset.i)] }); break;
      case "pick-service": {
        const m = S.masters[Number(el.dataset.m)];
        startBooking(S.view.salon, { id: m.id, name: m.name }, m.services[Number(el.dataset.s)]);
        break;
      }
      case "pick-date":
        b.date = el.dataset.date; b.time = null; b.showNearby = false;
        document.querySelectorAll(".date").forEach((x) => x.setAttribute("aria-pressed", String(x === el)));
        updateSum(); loadSlots();
        break;
      case "pick-time":
        b.time = el.dataset.time;
        document.querySelectorAll("#slots-box .slot").forEach((x) => x.setAttribute("aria-pressed", String(x === el)));
        updateSum();
        break;
      case "show-nearby": b.showNearby = true; loadNearby(); break;
      case "pick-near": {
        const it = b.near[Number(el.dataset.i)];
        const dur = b.service.duration_min;
        const svc = it.services.find((s) => s.name === b.service.name && s.duration_min === dur)
          || it.services.find((s) => s.duration_min === dur)
          || it.services.find((s) => s.name === b.service.name)
          || it.services[0];
        const salon = { id: it.salon_id, name: it.salon_name, address: it.address, phone: it.phone, kind: it.kind, district_id: b.salon.district_id };
        S.stack.pop();                       // joriy bron sahifasini almashtiramiz
        startBooking(salon, { id: it.master_id, name: it.master_name }, svc, b.date, el.dataset.time);
        break;
      }
      case "confirm": confirmBooking(); break;
      case "cancel": cancelSheet(el.dataset.no); break;
      case "review": reviewSheet(el.dataset.no); break;
    }
  });

  document.addEventListener("change", (e) => {
    if (e.target.id === "district") {
      S.districtId = Number(e.target.value);
      store.set("bq_district", String(S.districtId));
      loadSalons();
    }
  });

  render();
})();
