// BandQil — Usta (barber) paneli. Mijoz ilovasi va bron qilish mantig'iga tegmaydi;
// faqat o'ziga tegishli bronlarni /api/usta/* orqali ko'rsatadi va holatini o'zgartiradi.
(() => {
  "use strict";

  const TOKEN_KEY = "bq_usta_token";
  const app = document.getElementById("app");
  const toastEl = document.getElementById("toast");
  const $ = (sel, root = document) => root.querySelector(sel);

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
  const money = (n) => Number(n || 0).toLocaleString("uz-UZ") + " so'm";
  const todayStr = () => new Date().toLocaleDateString("sv-SE");
  const addDays = (dateStr, n) => {
    const d = new Date(dateStr + "T00:00:00");
    d.setDate(d.getDate() + n);
    return d.toLocaleDateString("sv-SE");
  };
  const dayLabel = (dateStr) => {
    const d = new Date(dateStr + "T00:00:00");
    const names = ["Yakshanba", "Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba"];
    const [y, m, day] = dateStr.split("-");
    return `${day}.${m} — ${names[d.getDay()]}`;
  };

  let toastTimer = null;
  function toast(msg) {
    toastEl.textContent = msg;
    toastEl.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toastEl.classList.remove("show"), 2600);
  }

  const KIND_THEME = { barbershop: "barber", beauty: "beauty" };
  const STATUS_LABEL = { booked: "Band", done: "Tugatildi", cancelled: "Bekor qilindi", no_show: "Kelmadi" };

  const S = {
    token: localStorage.getItem(TOKEN_KEY) || "",
    me: null,
    tab: "today",
    date: todayStr(),
    stats: null,
    weekRevenue: null,
    bookings: [],
  };

  async function api(path, opts = {}) {
    const res = await fetch(path, {
      ...opts,
      headers: { "Content-Type": "application/json", "X-Usta-Token": S.token, ...(opts.headers || {}) },
    });
    let data = null;
    try { data = await res.json(); } catch { /* bo'sh javob */ }
    if (!res.ok) {
      if (res.status === 403) { logout(false); throw new Error("Sessiya tugadi, qaytadan kiring"); }
      const msg = (data && (data.detail || data.message)) || `Xato (${res.status})`;
      throw new Error(msg);
    }
    return data;
  }

  function logout(callServer = true) {
    if (callServer && S.token) api("/api/usta/logout", { method: "POST" }).catch(() => {});
    localStorage.removeItem(TOKEN_KEY);
    S.token = ""; S.me = null;
    render();
  }

  // ---------- 0. Kirish ----------
  function renderLogin(error) {
    document.body.dataset.theme = "neutral";
    app.innerHTML = `
      <div class="usta-login">
        <header class="top"><span class="brand">BandQil</span></header>
        <h1>Usta paneli</h1>
        <p class="muted">Admin bergan telefon va parol bilan kiring.</p>
        <label class="field"><span>Telefon</span><input class="input" id="phone" placeholder="90 123 45 67" autocomplete="tel"></label>
        <label class="field"><span>Parol</span><input class="input" id="password" type="password" autocomplete="current-password"></label>
        ${error ? `<div class="admin-error" style="margin-top:12px;padding:12px 14px;background:rgba(216,50,60,.1);color:var(--pole);border-radius:12px;font-size:14px">${esc(error)}</div>` : ""}
        <button class="btn" id="go">Kirish</button>
      </div>`;
    $("#password").addEventListener("keydown", (e) => { if (e.key === "Enter") $("#go").click(); });
    $("#go").addEventListener("click", async () => {
      const phone = $("#phone").value.trim();
      const password = $("#password").value;
      if (!phone || !password) return;
      try {
        const { token } = await api("/api/usta/login", { method: "POST", body: JSON.stringify({ phone, password }) });
        S.token = token;
        localStorage.setItem(TOKEN_KEY, token);
        await boot();
      } catch (e) { renderLogin(e.message); }
    });
  }

  // ---------- qobiq ----------
  function shell(contentHtml) {
    app.innerHTML = `
      <div id="view">${contentHtml}</div>
      <nav class="tabs" id="tabs">
        <button data-tab="today" aria-current="${S.tab === "today" ? "page" : "false"}">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/></svg>
          Bugun
        </button>
        <button data-tab="profile" aria-current="${S.tab === "profile" ? "page" : "false"}">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 3.6-7 8-7s8 3 8 7"/></svg>
          Profil
        </button>
      </nav>`;
  }
  function loadingCard() { return `<div class="admin-card admin-empty" style="padding:16px;border:1px solid var(--line);border-radius:16px;text-align:center;color:var(--muted)">Yuklanmoqda…</div>`; }

  // ---------- 1. Bugungi panel ----------
  async function renderToday() {
    document.body.dataset.theme = (S.me && KIND_THEME[S.me.kind]) || "neutral";
    shell(loadingCard());
    try {
      S.stats = await api(`/api/usta/stats?date=${S.date}`);
      S.bookings = await api(`/api/usta/bookings?date=${S.date}`);
      if (S.weekRevenue === null || S.weekRevenueDate !== S.date) {
        const days = Array.from({ length: 7 }, (_, i) => addDays(S.date, -i));
        const sums = await Promise.all(days.map((d) => api(`/api/usta/stats?date=${d}`)));
        S.weekRevenue = sums.reduce((a, s) => a + s.revenue, 0);
        S.weekCount = sums.reduce((a, s) => a + s.done, 0);
        S.weekRevenueDate = S.date;
      }
    } catch (e) {
      shell(`<div class="admin-error" style="padding:14px;background:rgba(216,50,60,.1);color:var(--pole);border-radius:12px">${esc(e.message)}</div>`);
      return;
    }

    const now = new Date();
    const nowStr = now.toLocaleDateString("sv-SE") + " " + now.toTimeString().slice(0, 5);
    const current = S.bookings.find((b) => b.status === "booked" && b.start_at <= nowStr && b.end_at > nowStr);
    const next = !current ? S.bookings.find((b) => b.status === "booked" && b.start_at > nowStr) : null;
    const spotlight = current || next;

    shell(`
      <div class="usta-top">
        <span class="brand">${esc(S.me.name)}</span>
        <div class="date-nav">
          <button data-nav="-1" aria-label="Oldingi kun">‹</button>
          <input type="date" id="date-pick" value="${S.date}">
          <button data-nav="1" aria-label="Keyingi kun">›</button>
        </div>
      </div>
      <h1>${S.date === todayStr() ? "Salom!" : dayLabel(S.date)}</h1>
      <p class="muted">${esc(S.me.salon_name)}</p>

      <div class="usta-hero">
        <div class="usta-hero__label">${S.date === todayStr() ? "Bugungi savdo" : "Shu kungi savdo"}</div>
        <div class="usta-hero__amount">${money(S.stats.revenue)}</div>
        <div class="usta-hero__sub">Oxirgi 7 kun: ${money(S.weekRevenue)} · ${S.weekCount} mijoz</div>
      </div>

      <div class="usta-stats">
        <div class="usta-stat"><b>${S.stats.pending}</b><span>Kutilmoqda</span></div>
        <div class="usta-stat"><b>${S.stats.done}</b><span>Kelgan mijoz</span></div>
        <div class="usta-stat"><b>${S.stats.missed}</b><span>Bekor/kelmadi</span></div>
      </div>

      ${spotlight ? `
      <div class="usta-current">
        <span class="usta-current__badge">${current ? "Hozir kresloda" : "Keyingi mijoz"}</span>
        <div class="usta-current__time">${esc(spotlight.start_at.slice(11))} – ${esc(spotlight.end_at.slice(11))}</div>
        <div class="usta-current__name">${esc(spotlight.client_name)}</div>
        <div class="usta-current__contact"><a href="tel:${esc(spotlight.client_phone)}">${esc(spotlight.client_phone)}</a></div>
        <div class="usta-current__tags"><span>${esc(spotlight.service_name)}</span><span>${money(spotlight.price)}</span></div>
        <div class="usta-current__actions">
          <button class="btn btn--ok" data-action="st" data-no="${esc(spotlight.booking_no)}" data-status="done">✓ Tugatish</button>
          <button class="btn btn--quiet" data-action="st" data-no="${esc(spotlight.booking_no)}" data-status="no_show">Kelmadi</button>
          <button class="btn btn--quiet btn--danger" data-action="st" data-no="${esc(spotlight.booking_no)}" data-status="cancelled">Bekor</button>
        </div>
      </div>` : ""}

      <h2 class="section-title">Jadval</h2>
      <div class="usta-sched">
        ${S.bookings.length ? S.bookings.map((b) => `
          <div class="usta-sched__row">
            <span class="usta-sched__time">${esc(b.start_at.slice(11))}</span>
            <span class="usta-sched__body">
              <span class="usta-sched__name">${esc(b.client_name)}</span>
              <span class="usta-sched__svc">${esc(b.service_name)} · ${money(b.price)}</span>
            </span>
            <span class="usta-sched__status usta-sched__status--${b.status}">${STATUS_LABEL[b.status] || b.status}</span>
          </div>`).join("") : `<p class="muted" style="padding:16px 0">Bu kunga bron yo'q</p>`}
      </div>
    `);

    $("#date-pick").addEventListener("change", (e) => { S.date = e.target.value; renderToday(); });
    document.querySelectorAll("[data-nav]").forEach((btn) => {
      btn.addEventListener("click", () => { S.date = addDays(S.date, Number(btn.dataset.nav)); renderToday(); });
    });
    $("#view").addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-action='st']");
      if (!btn) return;
      btn.closest(".usta-current__actions").querySelectorAll("button").forEach((b) => (b.disabled = true));
      try {
        await api(`/api/usta/bookings/${btn.dataset.no}/status`, { method: "POST", body: JSON.stringify({ status: btn.dataset.status }) });
        toast("Yangilandi");
        renderToday();
      } catch (err) { toast(err.message); renderToday(); }
    });
  }

  // ---------- 2. Profil ----------
  function renderProfile() {
    document.body.dataset.theme = (S.me && KIND_THEME[S.me.kind]) || "neutral";
    shell(`
      <header class="top"><span class="brand">Profil</span></header>
      <div class="usta-profile">
        <div class="usta-profile__row"><span>Ism</span><span>${esc(S.me.name)}</span></div>
        <div class="usta-profile__row"><span>Salon</span><span>${esc(S.me.salon_name)}</span></div>
        <div class="usta-profile__row"><span>Manzil</span><span>${esc(S.me.address)}</span></div>
      </div>
      <button class="btn btn--quiet" id="logout" style="margin-top:16px">Chiqish</button>
    `);
    $("#logout").addEventListener("click", () => logout());
  }

  function render() {
    if (!S.token) { renderLogin(); return; }
    ({ today: renderToday, profile: renderProfile }[S.tab])();
  }

  document.addEventListener("click", (e) => {
    const tabBtn = e.target.closest("#tabs [data-tab]");
    if (tabBtn) { S.tab = tabBtn.dataset.tab; if (S.tab === "today") S.date = S.date || todayStr(); render(); }
  });

  async function boot() {
    try {
      S.me = await api("/api/usta/me");
      render();
    } catch (e) {
      S.token = "";
      localStorage.removeItem(TOKEN_KEY);
      renderLogin();
    }
  }

  boot();
})();
