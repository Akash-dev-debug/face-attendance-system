function showToast(message, type = "success") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const icons = {
    success: "✓",
    warning: "!",
    error: "✕",
  };

  const toast = document.createElement("div");
  toast.className = `toast ${type === "success" ? "" : type}`;
  toast.innerHTML = `
    <span class="toast-icon">${icons[type] || icons.success}</span>
    <span class="toast-text">${message}</span>
  `;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 200);
  }, 4000);
}