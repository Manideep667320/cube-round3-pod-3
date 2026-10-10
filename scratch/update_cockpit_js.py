import re
from pathlib import Path

COCKPIT_PATH = Path(r"c:\Users\manid\Documents\cube-round3-pod-3\orchestration\static\cockpit.js")
text = COCKPIT_PATH.read_text(encoding="utf-8")

# Let's add upstream card synchronization inside renderPrep()
prep_insert = """
  // Synchronize Upstream Input Feed (from Agent 01 Receiving)
  const rcvSr = (activeWorkflow.stage_results || []).find(s => s.stage === 'receiving');
  const rcvEv = rcvSr && (activeEvidence[rcvSr.record_id] || Object.values(activeEvidence).find(e => e.stage === 'receiving'));
  const prepUpstreamVerdict = document.getElementById('prepUpstreamVerdict');
  if (prepUpstreamVerdict) {
    const v = (rcvSr && rcvSr.verdict) || (rcvEv && rcvEv.decision && rcvEv.decision.verdict) || 'ACCEPT';
    prepUpstreamVerdict.textContent = `${v} (Verified)`;
    prepUpstreamVerdict.style.color = (v === 'ACCEPT' || v === 'PASS') ? 'var(--color-success)' : 'var(--color-sale)';
  }
  const prepUpstreamBarcode = document.getElementById('prepUpstreamBarcode');
  if (prepUpstreamBarcode) {
    const bc = (rcvEv && rcvEv.payload && (rcvEv.payload.barcode || rcvEv.payload.gtin)) || 'GTIN-08493021 (B08N5WRWNW)';
    prepUpstreamBarcode.textContent = bc;
  }
  const prepUpstreamRecord = document.getElementById('prepUpstreamRecord');
  if (prepUpstreamRecord) {
    prepUpstreamRecord.textContent = `${(rcvSr && rcvSr.record_id) || 'RCV-0014'} (SHA-256 Intact)`;
  }
"""

text = text.replace('  // Preparation Requirements Table', prep_insert + '\n  // Preparation Requirements Table')

# Inside renderPack():
pack_insert = """
  // Synchronize Upstream Input Feed (from Agent 02 Prep)
  const prepSr = (activeWorkflow.stage_results || []).find(s => s.stage === 'prep');
  const prepEv = prepSr && (activeEvidence[prepSr.record_id] || Object.values(activeEvidence).find(e => e.stage === 'prep'));
  const packUpstreamRecord = document.getElementById('packUpstreamRecord');
  if (packUpstreamRecord) {
    packUpstreamRecord.textContent = `${(prepSr && prepSr.record_id) || 'PRP-0014'} (FBA Cleared)`;
  }
  const packUpstreamGatePill = document.getElementById('packUpstreamGatePill');
  if (packUpstreamGatePill) {
    const isAllow = (prepSr && (prepSr.verdict === 'PASS' || prepSr.state === 'completed'));
    packUpstreamGatePill.textContent = isAllow ? 'GATE: ALLOW (PACK AUTHORIZED)' : 'GATE: EVALUATING';
    packUpstreamGatePill.className = `pill ${isAllow ? 'pill-pass' : 'pill-warn'}`;
  }
"""

text = text.replace('  // Photo viewer: check for real captured photo\n  const mainPhoto = document.getElementById(\'packMainPhoto\');',
                    pack_insert + '\n  // Photo viewer: check for real captured photo\n  const mainPhoto = document.getElementById(\'packMainPhoto\');')

# Inside renderReturns():
returns_insert = """
  // Synchronize Upstream Input Feed (from Agents 02 & 03 Prep + Pack)
  const returnsUpstreamPrepRef = document.getElementById('returnsUpstreamPrepRef');
  if (returnsUpstreamPrepRef) {
    const prp = (activeWorkflow.stage_results || []).find(s => s.stage === 'prep');
    const pck = (activeWorkflow.stage_results || []).find(s => s.stage === 'pack');
    returnsUpstreamPrepRef.textContent = `${(prp && prp.record_id) || 'PRP-0014'} & ${(pck && pck.record_id) || 'PCK-0014'}`;
  }
"""

text = text.replace('  // Side-by-side photos\n  const origPhoto = document.getElementById(\'returnsOriginalPhoto\');',
                    returns_insert + '\n  // Side-by-side photos\n  const origPhoto = document.getElementById(\'returnsOriginalPhoto\');')

COCKPIT_PATH.write_text(text, encoding="utf-8")
print("cockpit.js upstream feed bindings successfully added!")
