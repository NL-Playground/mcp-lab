"use strict";

// ---- 小工具 ----------------------------------------------------------------
const $ = (sel) => document.querySelector(sel);

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error((data && data.detail) || `HTTP ${res.status}`);
  }
  return data;
}

let me = null;   // 目前登入者
let meta = { roles: [], departments: [] };

const isAdmin = () => me && me.permission === "admin";

// ---- 畫面切換 --------------------------------------------------------------
function showLogin() {
  $("#app-view").classList.add("hidden");
  $("#login-view").classList.remove("hidden");
}

function showApp() {
  $("#login-view").classList.add("hidden");
  $("#app-view").classList.remove("hidden");
  $("#who").textContent = `${me.user_name} · ${me.permission} · ${me.department}`;
}

// ---- 登入 / 登出 -----------------------------------------------------------
$("#login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("#login-error").textContent = "";
  try {
    me = await api("/api/login", {
      method: "POST",
      body: JSON.stringify({
        email: $("#login-email").value.trim(),
        password: $("#login-password").value,
      }),
    });
    await afterLogin();
  } catch (err) {
    $("#login-error").textContent = err.message;
  }
});

$("#logout-btn").addEventListener("click", async () => {
  await api("/api/logout", { method: "POST" });
  me = null;
  showLogin();
});

async function afterLogin() {
  showApp();
  meta = await api("/api/meta");
  fillSelect($("#c-role"), meta.roles.map((r) => r.code));
  fillSelect($("#c-dept"), meta.departments);
  await loadUsers();
}

// ---- 使用者清單 ------------------------------------------------------------
async function loadUsers() {
  const users = await api("/api/users");
  const tbody = $("#users-table tbody");
  tbody.innerHTML = "";
  for (const u of users) tbody.appendChild(renderRow(u));
}

function renderRow(u) {
  const tr = document.createElement("tr");
  const last = u.last_login_at
    ? new Date(u.last_login_at).toLocaleString()
    : "—";

  tr.innerHTML = `
    <td>${u.user_id}</td>
    <td>${esc(u.user_name)}</td>
    <td>${esc(u.email)}</td>
    <td><span class="badge ${u.permission}">${u.permission}</span></td>
    <td>${esc(u.department)}</td>
    <td><span class="badge ${u.is_active ? "on" : "off"}">${u.is_active ? "啟用" : "停用"}</span></td>
    <td class="muted-cell">${last}</td>
  `;

  const actions = document.createElement("td");
  actions.className = "row-actions";

  if (isAdmin()) {
    // 變更權限
    const roleSel = document.createElement("select");
    fillSelect(roleSel, meta.roles.map((r) => r.code), u.permission);
    roleSel.addEventListener("change", () =>
      act(() =>
        api(`/api/users/${encodeURIComponent(u.email)}/role`, {
          method: "POST",
          body: JSON.stringify({ role: roleSel.value }),
        }),
        `已將 ${u.email} 權限改為 ${roleSel.value}`
      )
    );
    actions.appendChild(roleSel);

    // 啟用 / 停用
    const toggle = document.createElement("button");
    toggle.className = "ghost";
    toggle.textContent = u.is_active ? "停用" : "啟用";
    toggle.addEventListener("click", () =>
      act(() =>
        api(`/api/users/${encodeURIComponent(u.email)}/active`, {
          method: "POST",
          body: JSON.stringify({ is_active: !u.is_active }),
        }),
        `已${u.is_active ? "停用" : "啟用"} ${u.email}`
      )
    );
    actions.appendChild(toggle);
  }

  // 改密碼 (admin 可改任何人;一般人可改自己)
  if (isAdmin() || me.email === u.email) {
    const pw = document.createElement("button");
    pw.className = "ghost";
    pw.textContent = "改密碼";
    pw.addEventListener("click", async () => {
      const np = prompt(`為 ${u.email} 設定新密碼:`);
      if (!np) return;
      act(() =>
        api(`/api/users/${encodeURIComponent(u.email)}/password`, {
          method: "POST",
          body: JSON.stringify({ password: np }),
        }),
        `已更新 ${u.email} 的密碼`
      );
    });
    actions.appendChild(pw);
  }

  tr.appendChild(actions);
  return tr;
}

// 執行一個操作,成功後刷新清單並顯示訊息
async function act(fn, okMsg) {
  $("#app-msg").textContent = "";
  try {
    await fn();
    await loadUsers();
    $("#app-msg").textContent = okMsg;
    setTimeout(() => ($("#app-msg").textContent = ""), 3000);
  } catch (err) {
    alert(err.message);
    await loadUsers();
  }
}

// ---- 新增使用者 Modal ------------------------------------------------------
$("#new-user-btn").addEventListener("click", () => {
  if (!isAdmin()) {
    alert("需要 admin 權限才能新增使用者");
    return;
  }
  $("#create-error").textContent = "";
  $("#create-form").reset();
  $("#create-modal").classList.remove("hidden");
});

$("#create-cancel").addEventListener("click", () =>
  $("#create-modal").classList.add("hidden")
);

$("#create-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("#create-error").textContent = "";
  try {
    await api("/api/users", {
      method: "POST",
      body: JSON.stringify({
        user_name: $("#c-name").value.trim(),
        email: $("#c-email").value.trim(),
        password: $("#c-password").value,
        role: $("#c-role").value,
        department: $("#c-dept").value,
      }),
    });
    $("#create-modal").classList.add("hidden");
    await loadUsers();
    $("#app-msg").textContent = "已新增使用者";
    setTimeout(() => ($("#app-msg").textContent = ""), 3000);
  } catch (err) {
    $("#create-error").textContent = err.message;
  }
});

// ---- helpers ---------------------------------------------------------------
function fillSelect(sel, values, selected) {
  sel.innerHTML = "";
  for (const v of values) {
    const opt = document.createElement("option");
    opt.value = v;
    opt.textContent = v;
    if (v === selected) opt.selected = true;
    sel.appendChild(opt);
  }
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

// ---- 啟動:檢查是否已有 session --------------------------------------------
(async function init() {
  try {
    me = await api("/api/me");
    await afterLogin();
  } catch {
    showLogin();
  }
})();
