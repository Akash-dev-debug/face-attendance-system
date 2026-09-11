let currentUserId = null;
let pendingDetails = null;
let stream = null;
const TOTAL_SAMPLES = 20;

const canvas = document.getElementById("canvas");

document.getElementById("save-details-btn").addEventListener("click", async () => {
  const name = document.getElementById("name").value.trim();
  const reg_no = document.getElementById("reg_no").value.trim();
  const department = document.getElementById("department").value.trim();

  if (!name || !reg_no) {
    showToast("Don't forget to add a name and an ID before saving.", "warning");
    return;
  }

  pendingDetails = { name, reg_no, department };

  document.getElementById("details-panel").style.display = "none";
  document.getElementById("check-panel").style.display = "block";

  try {
    const video = document.getElementById("video");
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } });
    video.srcObject = stream;
    await new Promise((resolve) => (video.onloadedmetadata = resolve));
    runDuplicateCheck();
  } catch (err) {
    showToast("We need permission to use your camera. Please allow access and reload the page.", "error");
    document.getElementById("check-panel").style.display = "none";
    document.getElementById("details-panel").style.display = "block";
  }
});

function captureFrame(videoEl) {
  canvas.width = videoEl.videoWidth;
  canvas.height = videoEl.videoHeight;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(videoEl, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", 0.8);
}

async function runDuplicateCheck() {
  const statusEl = document.getElementById("check-status");
  const video = document.getElementById("video");
  statusEl.textContent = "Checking if this face is already registered...";

  await new Promise((resolve) => setTimeout(resolve, 1200));

  const imageData = captureFrame(video);

  const res = await fetch("/api/check_duplicate_face", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image: imageData }),
  });
  const data = await res.json();

  if (!data.face_found) {
    statusEl.textContent = "Can't see a face — center it in frame.";
    setTimeout(runDuplicateCheck, 1500);
    return;
  }

  if (data.duplicate) {
    showAlreadyRegistered(data.user);
    return;
  }

  await createUserAndProceed();
}

function showAlreadyRegistered(user) {
  document.getElementById("check-panel").style.display = "none";
  const modal = document.getElementById("duplicate-modal");
  document.getElementById("duplicate-modal-text").textContent =
    `This face is already registered as "${user.name}" (ID: ${user.reg_no}). Duplicate registration isn't allowed — head to Attendance instead.`;
  modal.style.display = "flex";
}

document.getElementById("duplicate-try-again-btn").addEventListener("click", () => {
  document.getElementById("duplicate-modal").style.display = "none";
  document.getElementById("details-panel").style.display = "block";
  document.getElementById("name").value = "";
  document.getElementById("reg_no").value = "";
  document.getElementById("department").value = "";

  if (stream) {
    stream.getTracks().forEach((t) => t.stop());
    stream = null;
  }
});

async function createUserAndProceed() {
  const res = await fetch("/api/register_user", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(pendingDetails),
  });
  const data = await res.json();

  if (!data.success) {
    showToast(data.message || "Could not save details.", "error");
    document.getElementById("check-panel").style.display = "none";
    document.getElementById("details-panel").style.display = "block";
    return;
  }

  currentUserId = data.user_id;
  document.getElementById("check-panel").style.display = "none";
  document.getElementById("capture-panel").style.display = "block";

  const video2 = document.getElementById("video2");
  video2.srcObject = stream; // reuse the same camera stream, no need to ask again
}

document.getElementById("start-capture-btn").addEventListener("click", async () => {
  const btn = document.getElementById("start-capture-btn");
  btn.disabled = true;
  const statusEl = document.getElementById("scan-status");
  const fill = document.getElementById("progress-fill");
  const video2 = document.getElementById("video2");

  let captured = 0;
  let attempts = 0;

  while (captured < TOTAL_SAMPLES && attempts < TOTAL_SAMPLES * 3) {
    attempts++;
    const imageData = captureFrame(video2);
    statusEl.textContent = `Capturing ${captured}/${TOTAL_SAMPLES}`;

    const res = await fetch("/api/capture_face", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: currentUserId, index: captured, image: imageData }),
    });
    const data = await res.json();

    if (data.success) {
      captured++;
      fill.style.width = `${(captured / TOTAL_SAMPLES) * 100}%`;
    } else {
      statusEl.textContent = "Can't see your face — center it in frame";
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }

  statusEl.textContent = "Training model...";
  await fetch("/api/train_model", { method: "POST" });

  statusEl.textContent = "Done!";
  showToast("Registration complete. The model has been trained.", "success");

  if (stream) stream.getTracks().forEach((t) => t.stop());

  setTimeout(() => {
    window.location.href = "/attendance";
  }, 1200);
});