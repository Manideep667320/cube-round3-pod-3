import re
from pathlib import Path

INDEX_PATH = Path(r"c:\Users\manid\Documents\cube-round3-pod-3\orchestration\static\index.html")
COCKPIT_PATH = Path(r"c:\Users\manid\Documents\cube-round3-pod-3\orchestration\static\cockpit.js")

index_text = INDEX_PATH.read_text(encoding="utf-8")
cockpit_text = COCKPIT_PATH.read_text(encoding="utf-8")

# 1. Clean the remaining 6 emojis in index.html
index_text = index_text.replace("btn.textContent = isFav ? '♥' : '♡';",
"""btn.innerHTML = isFav 
        ? '<svg class=\"nexa-svg-icon\" width=\"15\" height=\"15\" viewBox=\"0 0 24 24\" fill=\"currentColor\" stroke=\"none\"><path d=\"M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z\"/></svg>'
        : '<svg class=\"nexa-svg-icon\" width=\"15\" height=\"15\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\"><path d=\"M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z\"/></svg>';""")

index_text = index_text.replace("btn.textContent = '✓ Added';", "btn.textContent = 'Added';")
index_text = index_text.replace("🔍 Live Camera Capture", "Live Camera Capture")
index_text = index_text.replace("🔍 Live Capture (Grounding Available)", "Live Capture (Grounding Available)")
index_text = index_text.replace("🔍 Live Capture", "Live Capture")

# 2. Add Upstream Feed Card in Station 02 (Prep)
PREP_UPSTREAM_CARD = """
        <!-- UPSTREAM INPUT FEED: RECEIVED FROM AGENT 01 (RECEIVING) -->
        <div class="upstream-pipeline-card" id="prepUpstreamFeed">
          <div class="upstream-header-row">
            <div class="upstream-title">
              <span class="upstream-from-tag">INPUT FEED // FROM AGENT 01 RECEIVING</span>
              <span>Inbound Dock Clearance Passed as Input</span>
            </div>
            <span id="prepUpstreamStatusPill" class="pill pill-pass">INPUT RECEIVED & VERIFIED</span>
          </div>
          <div class="upstream-grid">
            <div class="upstream-field">
              <span class="upstream-label">Dock Decision</span>
              <span class="upstream-val" id="prepUpstreamVerdict" style="color: var(--color-success); font-weight: 700;">ACCEPT (Verified)</span>
            </div>
            <div class="upstream-field">
              <span class="upstream-label">Scanned GTIN / Barcode</span>
              <span class="upstream-val mono" id="prepUpstreamBarcode">GTIN-08493021 (B08N5WRWNW)</span>
            </div>
            <div class="upstream-field">
              <span class="upstream-label">Inbound SKU</span>
              <span class="upstream-val mono" id="prepUpstreamSku">SKU-LAMP-LED (Desk Lamp)</span>
            </div>
            <div class="upstream-field">
              <span class="upstream-label">Evidence Record</span>
              <span class="upstream-val mono" id="prepUpstreamRecord">RCV-0014 (SHA-256 Intact)</span>
            </div>
          </div>
        </div>
"""

# Insert right before <div class="meta-summary-card"> in prep
index_text = index_text.replace('<div class="meta-summary-card">\n          <div class="meta-item"><span class="meta-label">Linked Receiving</span>',
                                PREP_UPSTREAM_CARD + '\n        <div class="meta-summary-card">\n          <div class="meta-item"><span class="meta-label">Linked Receiving</span>')

# 3. Add Upstream Feed Card in Station 03 (Pack)
PACK_UPSTREAM_CARD = """
        <!-- UPSTREAM INPUT FEED: RECEIVED FROM AGENT 02 (PREP) -->
        <div class="upstream-pipeline-card" id="packUpstreamFeed">
          <div class="upstream-header-row">
            <div class="upstream-title">
              <span class="upstream-from-tag">INPUT FEED // FROM AGENT 02 PREP</span>
              <span>Amazon FBA Compliance Certificate Passed as Input</span>
            </div>
            <span id="packUpstreamGatePill" class="pill pill-pass">GATE: ALLOW (PACK AUTHORIZED)</span>
          </div>
          <div class="upstream-grid">
            <div class="upstream-field">
              <span class="upstream-label">Prep Certificate ID</span>
              <span class="upstream-val mono" id="packUpstreamRecord">PRP-0014 (FBA Cleared)</span>
            </div>
            <div class="upstream-field">
              <span class="upstream-label">Mandates Cleared</span>
              <span class="upstream-val" id="packUpstreamRules">Amazon Rules 101, 201, 301 Passed</span>
            </div>
            <div class="upstream-field">
              <span class="upstream-label">FNSKU Label Match</span>
              <span class="upstream-val mono" id="packUpstreamFnsku">X00DUMMY014 (Flat & Scannable)</span>
            </div>
            <div class="upstream-field">
              <span class="upstream-label">Packaging Safety</span>
              <span class="upstream-val" id="packUpstreamPolybag">Polybag Sealed + Warning Verified</span>
            </div>
          </div>
        </div>
"""

index_text = index_text.replace('<div class="meta-summary-card">\n          <div class="meta-item"><span class="meta-label">Linked Prep</span>',
                                PACK_UPSTREAM_CARD + '\n        <div class="meta-summary-card">\n          <div class="meta-item"><span class="meta-label">Linked Prep</span>')

# 4. Add Upstream Feed Card in Station 04 (Returns)
RETURNS_UPSTREAM_CARD = """
        <!-- UPSTREAM INPUT FEED: RECEIVED FROM AGENTS 02 & 03 (PREP & PACK) -->
        <div class="upstream-pipeline-card" id="returnsUpstreamFeed">
          <div class="upstream-header-row">
            <div class="upstream-title">
              <span class="upstream-from-tag">INPUT FEED // FROM AGENTS 02 & 03 PREP + PACK</span>
              <span>Pre-Shipment Baseline Inspection Proof Passed as Input</span>
            </div>
            <span id="returnsUpstreamBaselinePill" class="pill pill-pass">BASELINE ACTIVE FOR COMPARISON</span>
          </div>
          <div class="upstream-grid">
            <div class="upstream-field">
              <span class="upstream-label">Pre-Shipment Records</span>
              <span class="upstream-val mono" id="returnsUpstreamPrepRef">PRP-0014 & PCK-0014</span>
            </div>
            <div class="upstream-field">
              <span class="upstream-label">Outbound Carton</span>
              <span class="upstream-val" id="returnsUpstreamBox">Box #4 (Tamper-Evident Tape Sealed)</span>
            </div>
            <div class="upstream-field">
              <span class="upstream-label">Outbound BOM Baseline</span>
              <span class="upstream-val" id="returnsUpstreamBom">100% Items Present & Pristine</span>
            </div>
            <div class="upstream-field">
              <span class="upstream-label">Comparator Mode</span>
              <span class="upstream-val">Grounding Delta vs Returned Unit</span>
            </div>
          </div>
        </div>
"""

index_text = index_text.replace('<div class="meta-summary-card">\n          <div class="meta-item"><span class="meta-label">Order ID</span><span class="meta-value" id="returnsOrderId">',
                                RETURNS_UPSTREAM_CARD + '\n        <div class="meta-summary-card">\n          <div class="meta-item"><span class="meta-label">Order ID</span><span class="meta-value" id="returnsOrderId">')

# 5. Add Upstream Feed Card and Image Input for Station 05 (Recovery)
RECOVERY_UPSTREAM_CARD = """
        <!-- UPSTREAM INPUT FEED: RECEIVED FROM AGENTS 01 -> 02 -> 03 -> 04 -->
        <div class="upstream-pipeline-card" id="recoveryUpstreamFeed">
          <div class="upstream-header-row">
            <div class="upstream-title">
              <span class="upstream-from-tag">INPUT FEED // FROM COMPLETE CHAIN (AGENTS 01 &rarr; 02 &rarr; 03 &rarr; 04)</span>
              <span>Synthesized Multi-Agent Evidence Ledger Passed as Input</span>
            </div>
            <span class="pill pill-pass">FEE CONTRADICTION PROVEN</span>
          </div>
          <div class="upstream-grid">
            <div class="upstream-field">
              <span class="upstream-label">01 Receiving Dock Input</span>
              <span class="upstream-val">RCV-0014 &bull; ACCEPT (Manifest Matched)</span>
            </div>
            <div class="upstream-field">
              <span class="upstream-label">02 Amazon Prep Input</span>
              <span class="upstream-val">PRP-0014 &bull; PASS (Rules 101/102 Sealed)</span>
            </div>
            <div class="upstream-field">
              <span class="upstream-label">03 Fulfillment Pack Input</span>
              <span class="upstream-val">PCK-0014 &bull; SEAL (BOM Matched)</span>
            </div>
            <div class="upstream-field">
              <span class="upstream-label">04 ReturnGuard AI Input</span>
              <span class="upstream-val">RTN-0014 &bull; RESTOCK (Like New)</span>
            </div>
          </div>
        </div>
"""

index_text = index_text.replace('<div class="meta-summary-card">\n          <div class="meta-item"><span class="meta-label">Case ID</span>',
                                RECOVERY_UPSTREAM_CARD + '\n        <div class="meta-summary-card">\n          <div class="meta-item"><span class="meta-label">Case ID</span>')

# Update Recovery station action header with dedicated file input & connect phone camera:
RECOVERY_HEADER_ACTIONS = """
          <div class="btn-group">
            <input type="file" id="uploadInput_recovery" accept="image/*" style="display: none;" onchange="window.handleDirectUpload(event, 'recovery')">
            <button class="btn btn-secondary" onclick="document.getElementById('uploadInput_recovery').click()">Upload Dispute Photo</button>
            <button class="btn btn-secondary" onclick="window.openStationScanner('recovery')">Connect Phone Cam</button>
            <button class="btn btn-primary" onclick="generateDossier()">Generate SAFE-T Dossier &rarr;</button>
          </div>
"""

index_text = re.sub(r'<div class="btn-group">\s*<button class="btn btn-primary" onclick="generateDossier\(\)">Generate SAFE-T Dossier</button>\s*</div>',
                    RECOVERY_HEADER_ACTIONS.strip(),
                    index_text)

# Update Connect Phone Cam buttons on each station to call window.openStationScanner(stage):
index_text = index_text.replace('window.openStationScanner(\'receiving\')', "window.openStationScanner('receiving')")
index_text = index_text.replace('id="uploadInput_prep" accept="image/*" style="display: none;" onchange="window.handleDirectUpload(event, \'prep\')">\n            <button class="btn btn-secondary" onclick="document.getElementById(\'uploadInput_prep\').click()">📷 Upload Photo</button>',
                                'id="uploadInput_prep" accept="image/*" style="display: none;" onchange="window.handleDirectUpload(event, \'prep\')">\n            <button class="btn btn-secondary" onclick="document.getElementById(\'uploadInput_prep\').click()">Upload Photo</button>\n            <button class="btn btn-secondary" onclick="window.openStationScanner(\'prep\')">Connect Phone Cam</button>')

index_text = index_text.replace('id="uploadInput_pack" accept="image/*" style="display: none;" onchange="window.handleDirectUpload(event, \'pack\')">\n            <button class="btn btn-secondary" onclick="document.getElementById(\'uploadInput_pack\').click()">📷 Upload Photo</button>',
                                'id="uploadInput_pack" accept="image/*" style="display: none;" onchange="window.handleDirectUpload(event, \'pack\')">\n            <button class="btn btn-secondary" onclick="document.getElementById(\'uploadInput_pack\').click()">Upload Photo</button>\n            <button class="btn btn-secondary" onclick="window.openStationScanner(\'pack\')">Connect Phone Cam</button>')

index_text = index_text.replace('id="uploadInput_returns" accept="image/*" style="display: none;" onchange="window.handleDirectUpload(event, \'returns\')">\n            <button class="btn btn-secondary" onclick="document.getElementById(\'uploadInput_returns\').click()">📷 Upload Photo</button>',
                                'id="uploadInput_returns" accept="image/*" style="display: none;" onchange="window.handleDirectUpload(event, \'returns\')">\n            <button class="btn btn-secondary" onclick="document.getElementById(\'uploadInput_returns\').click()">Upload Photo</button>\n            <button class="btn btn-secondary" onclick="window.openStationScanner(\'returns\')">Connect Phone Cam</button>')

INDEX_PATH.write_text(index_text, encoding="utf-8")
print("index.html successfully updated with upstream cards and inputs!")

# -------------------------------------------------------------
# Now, clean emojis in cockpit.js and add openStationScanner & passOutputToNextStage
# -------------------------------------------------------------
# Replace emoji toasts and messages in cockpit.js:
cockpit_text = cockpit_text.replace('⚠️ Glare detected', 'Glare detected')
cockpit_text = cockpit_text.replace('⚠️ Motion blur detected', 'Motion blur detected')
cockpit_text = cockpit_text.replace('✓ Perfect sharpness', 'Optimal sharpness')
cockpit_text = cockpit_text.replace('✓ Signed override', 'Signed override')
cockpit_text = cockpit_text.replace('🛡️ Opened Cryptographic SAFE-T Claim Dossier', 'Opened Cryptographic SAFE-T Claim Dossier')
cockpit_text = cockpit_text.replace('✓ Formal dispute letter copied to clipboard!', 'Formal dispute letter copied to clipboard!')
cockpit_text = cockpit_text.replace('✓ Cryptographic JSON dossier copied to clipboard!', 'Cryptographic JSON dossier copied to clipboard!')
cockpit_text = cockpit_text.replace('🚀 Submitting dispute to Amazon Selling Partner API (SP-API)...', 'Submitting dispute to Amazon Selling Partner API (SP-API)...')
cockpit_text = cockpit_text.replace('✓ SAFE-T Claim Ticket #CASE-025-1182 Created! Reversal status: PENDING_CREDIT (+$25.00)', 'SAFE-T Claim Ticket #CASE-025-1182 Created! Reversal status: PENDING_CREDIT (+$25.00)')
cockpit_text = cockpit_text.replace('📤 Transmitting image to Orchestrator for', 'Transmitting image to Orchestrator for')
cockpit_text = cockpit_text.replace('✓ Orchestrator confirmed delivery!', 'Orchestrator confirmed delivery!')
cockpit_text = cockpit_text.replace('✓ CONTRADICTS (Claim Recommended)', 'CONTRADICTS (Claim Recommended)')
cockpit_text = cockpit_text.replace('📷 Photo received & routed by Orchestrator for', 'Photo received & routed by Orchestrator for')
cockpit_text = cockpit_text.replace('⚡ ${payload.data.stage', '${payload.data.stage')
cockpit_text = cockpit_text.replace('<span style="font-size: 16px;">⚡</span>', '<span class="stage-num-chip">EVENT</span>')

# Replace emoji camera placeholders in cockpit.js:
cockpit_text = cockpit_text.replace('<div style="font-size: 24px; margin-bottom: 8px;">📷</div>',
                                    '<div style="width: 32px; height: 32px; margin: 0 auto 8px; color: var(--color-accent-gold); display: flex; align-items: center; justify-content: center;"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg></div>')

# Add window.openStationScanner and window.passOutputToNextStage:
STAGE_HELPERS = """
// Open station-targeted phone camera scanner modal
window.openStationScanner = function(stage) {
  stage = stage || currentRoute || 'receiving';
  const qrImg = document.querySelector('#qrModal img');
  if (qrImg) {
    qrImg.src = `/api/scanner-qr?stage=${stage}&t=${Date.now()}`;
  }
  const modalTitle = document.getElementById('qrModalTitle');
  if (modalTitle) {
    modalTitle.textContent = `Connect Handheld Scanner (${stage.toUpperCase()} AGENT)`;
  }
  const hintEl = document.getElementById('qrUrlHint');
  if (hintEl && window._lanUrl) {
    hintEl.textContent = `${window._lanUrl}?stage=${stage}`;
  }
  const modal = document.getElementById('qrModal');
  if (modal) {
    modal.style.display = 'flex';
  }
  window.showToast(`Opened phone camera pairing for ${stage.toUpperCase()} agent`);
};

// Sequential Chaining: Pass output of one agent as input to the next agent
window.passOutputToNextStage = function(fromStage, toStage) {
  window.showToast(`Output from ${fromStage.toUpperCase()} passed as input context to ${toStage.toUpperCase()} agent.`);
  window.switchRoute(toStage);
  
  // Highlight the upstream input card on destination stage
  const upstreamCard = document.getElementById(`${toStage}UpstreamFeed`);
  if (upstreamCard) {
    upstreamCard.style.outline = '2px solid var(--color-accent-gold)';
    upstreamCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
    setTimeout(() => {
      upstreamCard.style.outline = 'none';
    }, 2400);
  }
};
"""

if "window.openStationScanner" not in cockpit_text:
  cockpit_text = STAGE_HELPERS + "\n" + cockpit_text

COCKPIT_PATH.write_text(cockpit_text, encoding="utf-8")
print("cockpit.js successfully updated with helper functions and clean text!")
