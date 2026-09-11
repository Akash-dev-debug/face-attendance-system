const dateFilter = document.getElementById("date-filter");
const searchFilter = document.getElementById("search-filter");
const recordsBody = document.getElementById("records-body");
const recordsEmpty = document.getElementById("records-empty");
let isAdmin = false;

async function checkAdminStatus() {
  const res = await fetch("/admin/status");
  const data = await res.json();
  isAdmin = data.is_admin;
  document.getElementById("admin-logged-out").style.display = isAdmin ? "none" : "block";
  document.getElementById("admin-logged-in").style.display = isAdmin ? "block" : "none";
}

document.getElementById("admin-login-btn").addEventListener("click", async () => {
  const password = document.getElementById("admin-password").value;
  const res = await fetch("/admin/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  const data = await res.json();
  if (data.success) {
    showToast("Logged in as admin.", "success");
    checkAdminStatus();
  } else {
    showToast(data.message || "Wrong password.", "error");
  }
});

document.getElementById("admin-logout-btn").addEventListener("click", async () => {
  await fetch("/admin/logout", { method: "POST" });
  checkAdminStatus();
  showToast("Logged out.", "success");
});

document.getElementById("clear-all-btn").addEventListener("click", async () => {
  if (!confirm("This deletes EVERY registered person and EVERY attendance record permanently. Continue?")) return;
  const res = await fetch("/api/clear_all", { method: "POST" });
  const data = await res.json();
  if (data.success) {
    showToast("All data cleared.", "success");
    setTimeout(() => window.location.reload(), 800);
  } else {
    showToast(data.message || "Failed.", "error");
  }
});

async function loadRecords() {
  const params = new URLSearchParams();
  if (dateFilter.value) params.append("date", dateFilter.value);
  if (searchFilter.value) params.append("search", searchFilter.value);
  const res = await fetch(`/api/records?${params.toString()}`);
  const records = await res.json();

  recordsBody.innerHTML = "";
  if (records.length === 0) {
    recordsEmpty.style.display = "block";
    return;
  }
  recordsEmpty.style.display = "none";
  for (const r of records) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${r.name}</td>
      <td class="mono">${r.reg_no}</td>
      <td>${r.department || "—"}</td>
      <td>${r.date}</td>
      <td class="mono">${r.time}</td>
      <td><span class="badge badge-success">${r.confidence ? r.confidence.toFixed(1) : "—"}</span></td>
    `;
    recordsBody.appendChild(row);
  }
}

dateFilter.addEventListener("change", loadRecords);
searchFilter.addEventListener("input", loadRecords);

document.getElementById("clear-filters-btn").addEventListener("click", () => {
  dateFilter.value = "";
  searchFilter.value = "";
  loadRecords();
});

document.getElementById("export-btn").addEventListener("click", () => {
  if (!isAdmin) { showToast("Admin login required to export.", "warning"); return; }
  const params = new URLSearchParams();
  if (dateFilter.value) params.append("date", dateFilter.value);
  if (searchFilter.value) params.append("search", searchFilter.value);
  window.location.href = `/api/export?${params.toString()}`;
});

document.querySelectorAll(".delete-user-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    if (!isAdmin) { showToast("Admin login required to remove people.", "warning"); return; }
    if (!confirm("Remove this person and their attendance history?")) return;
    const res = await fetch(`/api/users/${btn.dataset.id}`, { method: "DELETE" });
    const data = await res.json();
    if (data.success !== false) window.location.reload();
    else showToast(data.message, "error");
  });
});

checkAdminStatus();
loadRecords();