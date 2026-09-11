const video = document.getElementById("video");
const overlay = document.getElementById("overlay");
const captureCanvas = document.getElementById("capture-canvas");
const statusEl = document.getElementById("scan-status");
const recentList = document.getElementById("recent-list");

const markedThisSession = new Set();
const SCAN_INTERVAL_MS = 1500;
const registerModal = document.getElementById("register-modal");
let consecutiveUnknown = 0;
let modalShownRecently = false;

async function startCamera() {
  const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } });
  video.srcObject = stream;
  video.addEventListener("loadedmetadata", () => {
    overlay.width = video.videoWidth;
    overlay.height = video.videoHeight;
    statusEl.textContent = "Scanning...";
    setInterval(scanFrame, SCAN_INTERVAL_MS);
  });
}

function captureFrame() {
  captureCanvas.width = video.videoWidth;
  captureCanvas.height = video.videoHeight;
  const ctx = captureCanvas.getContext("2d");
  ctx.drawImage(video, 0, 0, captureCanvas.width, captureCanvas.height);
  return captureCanvas.toDataURL("image/jpeg", 0.8);
}

function drawBox(box, label, color) {
  const ctx = overlay.getContext("2d");
  ctx.clearRect(0, 0, overlay.width, overlay.height);
  if (!box) return;
  const [x, y, w, h] = box;
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.strokeRect(x, y, w, h);
  if (label) {
    ctx.font = "16px 'IBM Plex Mono', monospace";
    const textWidth = ctx.measureText(label).width;
    ctx.fillStyle = color;
    ctx.fillRect(x, y - 24, textWidth + 12, 22);
    ctx.fillStyle = "#12181B";
    ctx.fillText(label, x + 6, y - 8);
  }
}

async function scanFrame() {
  const imageData = captureFrame();
  const res = await fetch("/api/recognize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image: imageData }),
  });
  const data = await res.json();

  if (!data.face_found) {
    statusEl.textContent = "No face in frame";
    drawBox(null);
    return;
  }

   if (!data.recognized) {
    statusEl.textContent = "Face not recognized";
    drawBox(data.box, "Unknown", "#F2A93B");
    consecutiveUnknown++;
    if (consecutiveUnknown >= 3 && !modalShownRecently) {
      registerModal.style.display = "flex";
      modalShownRecently = true;
    }
    return;
  }
  consecutiveUnknown = 0;
  const user = data.user;
  drawBox(data.box, user.name, "#3CCF7A");

  if (data.status === "marked") {
    statusEl.textContent = `Checked in: ${user.name}`;
    if (!markedThisSession.has(user.id)) {
      markedThisSession.add(user.id);
      addToRecentList(user, data.time);
      showToast(`Attendance marked for ${user.name}`, "success");
    }
  } else {
    statusEl.textContent = `${user.name} — already checked in today`;
  }
}
document.getElementById("dismiss-modal-btn").addEventListener("click", () => {
  registerModal.style.display = "none";
  consecutiveUnknown = 0;
  setTimeout(() => { modalShownRecently = false; }, 15000);
});

function addToRecentList(user, time) {
  const emptyState = recentList.querySelector(".empty-state");
  if (emptyState) emptyState.remove();

  const row = document.createElement("div");
  row.style.display = "flex";
  row.style.justifyContent = "space-between";
  row.style.padding = "10px 0";
  row.style.borderBottom = "1px solid rgba(217,223,218,0.6)";
  row.innerHTML = `
    <span>${user.name} <span style="color:rgba(35,43,46,0.5); font-size:0.85rem;">(${user.reg_no})</span></span>
    <span class="mono" style="color:#1f8a4c;">${time}</span>
  `;
  recentList.prepend(row);
}

startCamera().catch(() => {
  statusEl.textContent = "Camera access denied";
  showToast("Please allow camera access to take attendance.", "error");
});