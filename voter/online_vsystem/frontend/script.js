// --- Simple router for sections ---
const sections = ["home", "userLogin", "partySection", "cameraSection", "adminLogin", "adminDashboard"];
function show(id) {
  sections.forEach(s => document.getElementById(s).classList.add("hidden"));
  document.getElementById(id).classList.remove("hidden");
}

// Nav clicks
document.addEventListener("click", (e) => {
  const to = e.target.dataset?.nav;
  if (!to) return;
  e.preventDefault();
  if (to === "home") show("home");
  if (to === "user") show("userLogin");
  if (to === "admin") show("adminLogin");
});

const api = (path, opts={}) => fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });

// --- USER LOGIN ---
let currentUser = { name: "", aadhar: "" };
document.getElementById("userLoginBtn").addEventListener("click", async () => {
  const name = document.getElementById("userName").value.trim();
  const aadhar = document.getElementById("userAadhar").value.trim();
  if (!name || aadhar.length !== 12) {
    alert("Enter valid Name and 12-digit Aadhaar");
    return;
  }
  const res = await api("/api/login-user", { method: "POST", body: JSON.stringify({ name, aadhar }) }).then(r=>r.json());
  if (!res.success) return alert(res.message || "Login failed");
  currentUser = { name, aadhar };
  await loadParties();
  show("partySection");
});

// --- LOAD PARTY TABLE ---
async function loadParties() {
  const tbody = document.getElementById("partyTableBody");
  tbody.innerHTML = "<tr><td colspan='3'>Loading...</td></tr>";
  const parties = await api("/api/parties").then(r => r.json());
  tbody.innerHTML = "";
  parties.forEach(p => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${p.name}</td>
      <td>${p.logo}</td>
      <td><button data-party="${p.name}">Select</button></td>
    `;
    tbody.appendChild(tr);
  });

  // handle select clicks
  tbody.querySelectorAll("button[data-party]").forEach(btn => {
    btn.addEventListener("click", () => {
      selectedParty = btn.dataset.party;
      startCamera();
      // Prefill verify fields
      document.getElementById("verifyName").value = currentUser.name;
      document.getElementById("verifyAadhar").value = currentUser.aadhar;
      show("cameraSection");
    });
  });
}

let selectedParty = "";

// --- CAMERA ---
let mediaStream = null;
async function startCamera() {
  try {
    if (mediaStream) return; // already running
    mediaStream = await navigator.mediaDevices.getUserMedia({ video: true });
    document.getElementById("video").srcObject = mediaStream;
  } catch (e) {
    console.error("Camera error", e);
    alert("Unable to access camera. Please allow camera permission.");
  }
}

// --- CAPTURE & VERIFY ---
document.getElementById("captureBtn").addEventListener("click", async () => {
  const vName = document.getElementById("verifyName").value.trim();
  const vAadhar = document.getElementById("verifyAadhar").value.trim();
  if (vName !== currentUser.name || vAadhar !== currentUser.aadhar) {
    return (document.getElementById("verifyResult").innerText = "Entered details do not match your login.");
  }
  if (!selectedParty) {
    return (document.getElementById("verifyResult").innerText = "Please select a party first.");
  }

  const video = document.getElementById("video");
  const canvas = document.getElementById("canvas");
  const ctx = canvas.getContext("2d");
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  const dataURL = canvas.toDataURL("image/jpeg");

  document.getElementById("verifyResult").innerText = "Verifying...";

  try {
    const res = await api("/api/verify-and-vote", {
      method: "POST",
      body: JSON.stringify({
        name: currentUser.name,
        aadhar: currentUser.aadhar,
        party: selectedParty,
        image: dataURL
      })
    }).then(r => r.json());

    document.getElementById("verifyResult").innerText = res.message || "Done";
  } catch (e) {
    console.error(e);
    document.getElementById("verifyResult").innerText = "Error contacting server.";
  }
});

// --- ADMIN ---
document.getElementById("adminLoginBtn").addEventListener("click", async () => {
  const username = document.getElementById("adminUser").value.trim();
  const password = document.getElementById("adminPass").value.trim();
  const res = await api("/api/admin/login", {
    method: "POST",
    body: JSON.stringify({ username, password })
  }).then(r=>r.json());
  if (!res.success) return alert(res.message || "Login failed");
  await loadAdminSummary();
  show("adminDashboard");
});

async function loadAdminSummary() {
  const data = await api("/api/admin/summary").then(r => r.json());
  const pretty =
    `Previous Elections:\n${JSON.stringify(data.previous, null, 2)}\n\n` +
    `Upcoming Elections:\n${JSON.stringify(data.upcoming, null, 2)}\n\n` +
    `Live Tallies:\n${JSON.stringify(data.live || {}, null, 2)}\n`;
  document.getElementById("adminData").textContent = pretty;
}
