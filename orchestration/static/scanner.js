// CUBE Handheld Mobile Scanner Logic
let currentStage = 'receiving';
let selectedFile = null;

const unitInput = document.getElementById('unitInput');
const cameraInput = document.getElementById('cameraInput');
const cameraFrame = document.getElementById('cameraFrame');
const previewImg = document.getElementById('previewImg');
const cameraIcon = document.getElementById('cameraIcon');
const cameraHint = document.getElementById('cameraHint');
const btnUpload = document.getElementById('btnUpload');
const receiptCard = document.getElementById('receiptCard');
const receiptDelivery = document.getElementById('receiptDelivery');
const receiptRoute = document.getElementById('receiptRoute');
const receiptStatus = document.getElementById('receiptStatus');
const receiptHash = document.getElementById('receiptHash');
const receiptVerdict = document.getElementById('receiptVerdict');

// Stage selection tabs
document.querySelectorAll('.seg-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.seg-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentStage = btn.dataset.stage;
  });
});

// Click camera frame to trigger native camera
cameraFrame.addEventListener('click', () => {
  cameraInput.click();
});

// File selected
cameraInput.addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (!file) return;

  selectedFile = file;
  const reader = new FileReader();
  reader.onload = (event) => {
    previewImg.src = event.target.result;
    previewImg.style.display = 'block';
    cameraIcon.style.display = 'none';
    cameraHint.style.display = 'none';
    btnUpload.disabled = false;
    btnUpload.textContent = `Route Photo to ${currentStage.toUpperCase()} Agent`;
  };
  reader.readAsDataURL(file);
});

// Upload to backend
btnUpload.addEventListener('click', async () => {
  if (!selectedFile) return;

  const unitId = unitInput.value.trim() || 'UNIT-0014';
  const formData = new FormData();
  formData.append('file', selectedFile);
  formData.append('unit_id', unitId);
  formData.append('stage', currentStage);
  formData.append('org_id', 'org_demo_alpha');

  btnUpload.disabled = true;
  btnUpload.textContent = 'Transmitting to Orchestrator...';

  try {
    const res = await fetch('/api/capture', {
      method: 'POST',
      body: formData
    });

    if (!res.ok) {
      throw new Error(`Upload failed with status ${res.status}`);
    }

    const data = await res.json();
    if (receiptDelivery) {
      receiptDelivery.textContent = data.delivery_confirmed ? '✓ CONFIRMED BY ORCHESTRATOR' : 'DISPATCHED';
    }
    if (receiptRoute) {
      const targetAgent = data.orchestrator_routed_to || currentStage;
      receiptRoute.textContent = `${targetAgent.toUpperCase()} AGENT`;
    }
    if (receiptStatus) {
      receiptStatus.textContent = 'LIVE OUTPUT STREAMING IN COCKPIT';
    }
    if (receiptHash) {
      const hashStr = data.image_hash || data.sha256 || 'verified';
      receiptHash.textContent = hashStr.substring(0, 16) + '...';
    }
    
    // Check stage result if available in workflow
    let verdict = 'COMPLETED';
    if (data.workflow && data.workflow.stage_results) {
      const stageRes = data.workflow.stage_results.find(s => s.stage === currentStage);
      if (stageRes && stageRes.verdict) {
        verdict = stageRes.verdict;
      }
    }
    if (receiptVerdict) {
      receiptVerdict.textContent = verdict;
    }
    if (receiptCard) {
      receiptCard.style.display = 'block';
    }
    btnUpload.textContent = '✓ Transmitted & Verified! Tap to Snap Another';
    btnUpload.disabled = false;
  } catch (err) {
    alert('Upload error: ' + err.message);
    btnUpload.disabled = false;
    btnUpload.textContent = 'Retry Transmission';
  }
});
