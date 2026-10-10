import re
from pathlib import Path

SRC = Path(r"c:\Users\manid\Documents\cube-round3-pod-3\orchestration\static\index.html")
text = SRC.read_text(encoding="utf-8")

# 1. Replace logo icon ▲ with clean minimalist SVG monogram or geometric mark
text = text.replace('<div class="logo-icon">▲</div>',
                    '<div class="logo-icon" style="display:flex;align-items:center;justify-content:center;"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="12 3 22 21 2 21"/></svg></div>')

text = text.replace('<div class="landing-brand-logo" style="width: 26px; height: 26px; font-size: 12px; background: var(--color-text-primary); color: var(--color-accent-gold); border: 1px solid var(--color-accent-gold);">▲</div>',
                    '<div class="landing-brand-logo" style="width: 26px; height: 26px; display:flex; align-items:center; justify-content:center; background: var(--color-text-primary); color: var(--color-accent-gold); border: 1px solid var(--color-accent-gold);"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="12 3 22 21 2 21"/></svg></div>')

# 2. Sidebar Navigation items:
text = text.replace('<span class="nav-item-icon">🌐</span>\n        <span>Landing Page</span>',
                    '<span class="nav-item-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg></span>\n        <span>Landing Page</span>')

text = text.replace('<span class="nav-item-icon">▦</span>\n        <span>Overview</span>',
                    '<span class="nav-item-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg></span>\n        <span>Overview</span>')

text = text.replace('<span class="nav-item-icon">⚡</span>\n        <span>Active Operations</span>',
                    '<span class="nav-item-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg></span>\n        <span>Active Operations</span>')

text = text.replace('<span class="nav-item-icon">📇</span>\n        <span>Product Passports</span>',
                    '<span class="nav-item-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><line x1="15" y1="8" x2="17" y2="8"/><line x1="15" y1="12" x2="17" y2="12"/><line x1="7" y1="16" x2="17" y2="16"/></svg></span>\n        <span>Product Passports</span>')

# Stage icons in sidebar: replace with clean numbered badges 01, 02, 03, 04, 05
text = text.replace('<span class="nav-item-icon">📥</span>\n        <span>01 Receiving</span>',
                    '<span class="nav-stage-badge">01</span>\n        <span>01 Receiving</span>')

text = text.replace('<span class="nav-item-icon">🏷️</span>\n        <span>02 Prep</span>',
                    '<span class="nav-stage-badge">02</span>\n        <span>02 Prep</span>')

text = text.replace('<span class="nav-item-icon">📦</span>\n        <span>03 Pack</span>',
                    '<span class="nav-stage-badge">03</span>\n        <span>03 Pack</span>')

text = text.replace('<span class="nav-item-icon">🔄</span>\n        <span>04 Returns</span>',
                    '<span class="nav-stage-badge">04</span>\n        <span>04 Returns</span>')

text = text.replace('<span class="nav-item-icon">🛡️</span>\n        <span>05 Recovery</span>',
                    '<span class="nav-stage-badge">05</span>\n        <span>05 Recovery</span>')

# System navigation items:
text = text.replace('<span class="nav-item-icon">⏱️</span>\n        <span>Event Timeline</span>',
                    '<span class="nav-item-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg></span>\n        <span>Event Timeline</span>')

text = text.replace('<span class="nav-item-icon">📚</span>\n        <span>Evidence Library</span>',
                    '<span class="nav-item-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg></span>\n        <span>Evidence Library</span>')

text = text.replace('<span class="nav-item-icon">📋</span>\n        <span>Review Queue</span>',
                    '<span class="nav-item-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/></svg></span>\n        <span>Review Queue</span>')

text = text.replace('<span class="nav-item-icon">⚖️</span>\n        <span>Rules & Requirements</span>',
                    '<span class="nav-item-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 3v18"/><path d="M5 8h14"/><path d="M4 14l3-6 3 6a3 3 0 0 1-6 0z"/><path d="M14 14l3-6 3 6a3 3 0 0 1-6 0z"/></svg></span>\n        <span>Rules & Requirements</span>')

text = text.replace('<span class="nav-item-icon">⚙️</span>\n        <span>Settings</span>',
                    '<span class="nav-item-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg></span>\n        <span>Settings</span>')

# 3. Top Header search and action buttons:
text = text.replace('<span class="search-icon">🔍</span>',
                    '<span class="search-icon"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg></span>')

text = text.replace('<span>🌐</span> Landing Page',
                    '<span>Landing Page</span>')

text = text.replace('<span>📱</span> Connect Phone Scanner',
                    '<span><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:middle;margin-right:4px;"><rect x="5" y="2" width="14" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg>Connect Phone Scanner</span>')

text = text.replace('<button class="header-icon-btn" title="Notifications" data-route="overview">🔔</button>',
                    '<button class="header-icon-btn" title="Notifications" data-route="overview"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg></button>')

text = text.replace('<button class="header-icon-btn" title="Documentation" data-route="prep">📖</button>',
                    '<button class="header-icon-btn" title="Documentation" data-route="prep"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg></button>')

text = text.replace('<button class="header-icon-btn" title="Settings" data-route="overview">⚙️</button>',
                    '<button class="header-icon-btn" title="Settings" data-route="overview"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg></button>')

# 4. Landing header search, wishlist, cart:
text = text.replace('<span class="nexa-search-icon">🔍</span>',
                    '<span class="nexa-search-icon"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg></span>')

text = text.replace('<span>♥</span>',
                    '<span><svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg></span>')

text = text.replace('<span>🛒</span>',
                    '<span><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 0 1-8 0"/></svg></span>')

# 5. Hero Eyebrow & Badges:
text = text.replace('<span>✦</span>\n                <span>DISCOVER · SHOP · BE INSPIRED</span>',
                    '<span class="nexa-bullet">●</span>\n                <span>DISCOVER · SHOP · BE INSPIRED</span>')

text = text.replace('★ 4.9 Rating', '4.9 Rating')
text = text.replace('★ 4.9', '4.9')
text = text.replace('★ 4.8', '4.8')
text = text.replace('★ 5.0', '5.0')
text = text.replace('★ 4.7', '4.7')

text = text.replace('<span>✨</span>\n                <span>New Arrivals · Up to 40% Off</span>',
                    '<span class="stage-num-chip">CURATED</span>\n                <span>New Arrivals · Up to 40% Off</span>')

text = text.replace('<span>✓</span>\n                <span>Autonomous Vision Inspected</span>',
                    '<span class="stage-num-chip">VERIFIED</span>\n                <span>Autonomous Vision Inspected</span>')

# Wishlist toggle buttons (♡ -> SVG heart outline):
text = re.sub(r'<button class="nexa-wishlist-toggle" onclick="toggleWishlist\(this, \'([^\']+)\'\)">♡</button>',
              r'<button class="nexa-wishlist-toggle" onclick="toggleWishlist(this, \'\1\')"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg></button>',
              text)

# 6. Bento Pillar Boxes (Replace 📱, ⚖️, 🔐, 🛡️):
text = text.replace('<div class="bento-icon-box" style="background: rgba(219, 234, 254, 0.7); color: #2563eb;">📱</div>',
                    '<div class="bento-icon-box" style="background: rgba(219, 234, 254, 0.7); color: #2563eb;"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="5" y="2" width="14" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg></div>')

text = text.replace('<div class="bento-icon-box" style="background: rgba(220, 252, 231, 0.7); color: #16a34a;">⚖️</div>',
                    '<div class="bento-icon-box" style="background: rgba(220, 252, 231, 0.7); color: #16a34a;"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3v18"/><path d="M5 8h14"/><path d="M4 14l3-6 3 6a3 3 0 0 1-6 0z"/><path d="M14 14l3-6 3 6a3 3 0 0 1-6 0z"/></svg></div>')

text = text.replace('<div class="bento-icon-box" style="background: rgba(243, 232, 255, 0.7); color: #7c3aed;">🔐</div>',
                    '<div class="bento-icon-box" style="background: rgba(243, 232, 255, 0.7); color: #7c3aed;"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg></div>')

text = text.replace('<div class="bento-icon-box" style="background: rgba(254, 226, 226, 0.7); color: #dc2626;">🛡️</div>',
                    '<div class="bento-icon-box" style="background: rgba(254, 226, 226, 0.7); color: #dc2626;"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg></div>')

# 7. Agent Showcase Grid on Landing:
text = text.replace('<span style="font-size: 18px;">📥</span>', '<span class="stage-num-chip">01</span>')
text = text.replace('<span style="font-size: 18px;">🏷️</span>', '<span class="stage-num-chip">02</span>')
text = text.replace('<span style="font-size: 18px;">📦</span>', '<span class="stage-num-chip">03</span>')
text = text.replace('<span style="font-size: 18px;">🔄</span>', '<span class="stage-num-chip">04</span>')
text = text.replace('<span style="font-size: 18px;">🛡️</span>', '<span class="stage-num-chip">05</span>')
text = text.replace('<span style="font-size: 18px;">🚀</span>', '<span class="stage-num-chip">ALL</span>')

# 8. Digital Product Passport section checks on landing:
text = text.replace('<span style="color: var(--success);">✓</span>', '<span style="color: var(--success); font-weight:700;">PASS</span>')
text = text.replace('<span style="color: var(--warning);">⚠</span>', '<span style="color: var(--color-accent-gold); font-weight:700;">REVIEW</span>')
text = text.replace('<span style="color: var(--accent-blue);">⚖</span>', '<span style="color: var(--color-accent-gold); font-weight:700;">CLAIM</span>')
text = text.replace('<span>📱 Connect Handheld Scanner</span>', '<span>Connect Handheld Scanner</span>')
text = text.replace('Product Passports 📇', 'Product Passports')

# 9. Overview Page Header & KPI Cards:
text = text.replace('<h1>Autonomous Operations Cockpit 👋</h1>', '<h1>Autonomous Operations Cockpit</h1>')

text = text.replace('<div class="kpi-icon" style="background: rgba(183, 138, 89, 0.12); color: var(--color-accent-gold);">📦</div>',
                    '<div class="kpi-icon" style="background: rgba(183, 138, 89, 0.12); color: var(--color-accent-gold);"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg></div>')

text = text.replace('<div class="kpi-icon" style="background: rgba(194, 142, 58, 0.12); color: var(--color-accent-gold);">⚠️</div>',
                    '<div class="kpi-icon" style="background: rgba(194, 142, 58, 0.12); color: var(--color-accent-gold);"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg></div>')

text = text.replace('<div class="kpi-icon" style="background: rgba(104, 129, 93, 0.12); color: var(--color-success);">✓</div>',
                    '<div class="kpi-icon" style="background: rgba(104, 129, 93, 0.12); color: var(--color-success);"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg></div>')

text = text.replace('<div class="kpi-icon" style="background: rgba(179, 78, 61, 0.12); color: var(--color-sale);">⛔</div>',
                    '<div class="kpi-icon" style="background: rgba(179, 78, 61, 0.12); color: var(--color-sale);"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg></div>')

text = text.replace('<span style="font-size: 16px;">🏆</span>', '<span class="stage-num-chip">FEDERATION</span>')

# 5 Agent Cards in Overview:
text = text.replace('<span style="font-size: 20px;">📥</span>', '<span class="stage-num-chip">01</span>')
text = text.replace('<span style="font-size: 20px;">🏷️</span>', '<span class="stage-num-chip">02</span>')
text = text.replace('<span style="font-size: 20px;">📦</span>', '<span class="stage-num-chip">03</span>')
text = text.replace('<span style="font-size: 20px;">🔄</span>', '<span class="stage-num-chip">04</span>')
text = text.replace('<span style="font-size: 20px;">🛡️</span>', '<span class="stage-num-chip">05</span>')

# Quick actions ribbon in Overview:
text = text.replace('<button class="quick-action-btn" data-route="receiving"><span>📥</span> 01 Receiving</button>',
                    '<button class="quick-action-btn" data-route="receiving"><span class="stage-num-chip">01</span> Receiving</button>')
text = text.replace('<button class="quick-action-btn" data-route="prep"><span>🏷️</span> 02 Prep</button>',
                    '<button class="quick-action-btn" data-route="prep"><span class="stage-num-chip">02</span> Prep</button>')
text = text.replace('<button class="quick-action-btn" data-route="pack"><span>📦</span> 03 Pack</button>',
                    '<button class="quick-action-btn" data-route="pack"><span class="stage-num-chip">03</span> Pack</button>')
text = text.replace('<button class="quick-action-btn" data-route="returns"><span>🔄</span> 04 Returns</button>',
                    '<button class="quick-action-btn" data-route="returns"><span class="stage-num-chip">04</span> Returns</button>')
text = text.replace('<button class="quick-action-btn" data-route="recovery"><span>🛡️</span> 05 Recovery</button>',
                    '<button class="quick-action-btn" data-route="recovery"><span class="stage-num-chip">05</span> Recovery</button>')

# 10. Station 01 Receiving:
text = text.replace('<span class="feature-chip">⚡ 4-State Physical Actions</span>', '<span class="feature-chip">4-State Physical Actions</span>')
text = text.replace('<span class="feature-chip">🔍 OpenCV Quality + zxing-cpp</span>', '<span class="feature-chip">OpenCV Quality + zxing-cpp</span>')
text = text.replace('<span class="feature-chip">🧭 coach.py Retake Assistant</span>', '<span class="feature-chip">coach.py Retake Assistant</span>')
text = text.replace('<span class="feature-chip">📊 91.4% Benchmark Accuracy</span>', '<span class="feature-chip">91.4% Benchmark Accuracy</span>')
text = text.replace('📷 Upload Photo', 'Upload Photo')
text = text.replace('🧭 Retake Coach', 'Retake Coach')
text = text.replace('<div style="font-size: 38px; margin-bottom: 10px;">📷</div>',
                    '<div style="width: 44px; height: 44px; margin: 0 auto 10px; display: flex; align-items: center; justify-content: center; color: var(--color-accent-gold);"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg></div>')

text = text.replace('<button class="btn btn-secondary btn-sm" onclick="document.getElementById(\'btnPairPhone\').click()">📱 Connect Phone Scanner</button>',
                    '<button class="btn btn-secondary btn-sm" onclick="window.openStationScanner(\'receiving\')">Connect Phone Scanner</button>')

text = text.replace('<div class="thumb-box thumb-add" onclick="document.getElementById(\'btnPairPhone\').click()">\n                  <span>📱</span> Phone Cam\n                </div>',
                    '<div class="thumb-box thumb-add" onclick="window.openStationScanner(\'receiving\')">\n                  <span>Phone Cam</span>\n                </div>')

text = text.replace('<span class="coach-title"><span>🧭</span> Retake Coach Advice (coach.py)</span>',
                    '<span class="coach-title">Retake Coach Advice (coach.py)</span>')

text = text.replace('<button class="btn btn-secondary btn-sm" onclick="window.applyReceivingOverride(\'VISUAL_CHECK_OK\')">✓ Visual Check OK</button>',
                    '<button class="btn btn-secondary btn-sm" onclick="window.applyReceivingOverride(\'VISUAL_CHECK_OK\')">Visual Check OK</button>')
text = text.replace('<button class="btn btn-secondary btn-sm" onclick="window.applyReceivingOverride(\'DOC_CORRECTED\')">📄 Doc Corrected</button>',
                    '<button class="btn btn-secondary btn-sm" onclick="window.applyReceivingOverride(\'DOC_CORRECTED\')">Doc Corrected</button>')
text = text.replace('<button class="btn btn-secondary btn-sm" onclick="window.applyReceivingOverride(\'SUPPLIER_APPROVED\')">🏢 Supplier OK</button>',
                    '<button class="btn btn-secondary btn-sm" onclick="window.applyReceivingOverride(\'SUPPLIER_APPROVED\')">Supplier OK</button>')

# Receiving button to pass output to next agent:
text = text.replace('<button class="btn btn-primary" data-route="prep">Continue to Prep →</button>',
                    '<button class="btn btn-primary" onclick="window.passOutputToNextStage(\'receiving\', \'prep\')">Pass Output to Agent 02 (Prep) →</button>')

text = text.replace('<div id="receivingBannerTitle" style="font-weight: 700; color: #166534; font-size: 12px; margin-bottom: 4px;">Proceed to Prep →</div>',
                    '<div id="receivingBannerTitle" style="font-weight: 700; color: #166534; font-size: 12px; margin-bottom: 4px;">Pass Receiving Output to Agent 02 (Prep) →</div>')

# 11. Station 02 Prep:
text = text.replace('<span class="feature-chip">📜 Amazon Rules 101–601</span>', '<span class="feature-chip">Amazon Rules 101–601</span>')
text = text.replace('<span class="feature-chip">🎯 Visual Grounding BBoxes</span>', '<span class="feature-chip">Visual Grounding BBoxes</span>')
text = text.replace('<span class="feature-chip">⚡ 1 Batched VLM (&lt;800ms)</span>', '<span class="feature-chip">1 Batched VLM (&lt;800ms)</span>')
text = text.replace('<span class="feature-chip">🚪 Cartonization Gate: ALLOW</span>', '<span class="feature-chip">Cartonization Gate: ALLOW</span>')

text = text.replace('<button class="btn btn-secondary" id="btnToggleBBoxes" onclick="window.togglePrepBBoxes()">🎯 Toggle Grounding Boxes</button>',
                    '<button class="btn btn-secondary" id="btnToggleBBoxes" onclick="window.togglePrepBBoxes()">Toggle Grounding Boxes</button>')

text = text.replace('<div style="font-size: 38px; margin-bottom: 10px;">🏷️</div>',
                    '<div style="width: 44px; height: 44px; margin: 0 auto 10px; display: flex; align-items: center; justify-content: center; color: var(--color-accent-gold);"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg></div>')

# Prep button to pass output to next agent:
text = text.replace('<button class="btn btn-primary" data-route="pack">Continue to Pack →</button>',
                    '<button class="btn btn-primary" onclick="window.passOutputToNextStage(\'prep\', \'pack\')">Pass Output to Agent 03 (Pack) →</button>')

# 12. Station 03 Pack:
text = text.replace('<div style="font-size: 38px; margin-bottom: 10px;">📦</div>',
                    '<div style="width: 44px; height: 44px; margin: 0 auto 10px; display: flex; align-items: center; justify-content: center; color: var(--color-accent-gold);"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg></div>')

text = text.replace('<button class="btn btn-secondary btn-sm" style="width: 100%;" onclick="showToast(\'Printing Shipping Label & Barcode\')">🖨️ Print Shipping Label</button>',
                    '<button class="btn btn-secondary btn-sm" style="width: 100%;" onclick="showToast(\'Printing Shipping Label & Barcode\')">Print Shipping Label</button>')

text = text.replace('<div id="packCheckPresent" style="font-size: 13px; font-weight: 800; color: #16a34a; margin-top: 2px;">✓ PASS</div>',
                    '<div id="packCheckPresent" style="font-size: 13px; font-weight: 800; color: #16a34a; margin-top: 2px;">PASS</div>')

text = text.replace('<div id="packCheckQty" style="font-size: 13px; font-weight: 800; color: #16a34a; margin-top: 2px;">✓ 1/1 MATCH</div>',
                    '<div id="packCheckQty" style="font-size: 13px; font-weight: 800; color: #16a34a; margin-top: 2px;">1/1 MATCH</div>')

text = text.replace('<div id="packCheckExtra" style="font-size: 13px; font-weight: 800; color: #16a34a; margin-top: 2px;">✓ 0 UNEXPECTED</div>',
                    '<div id="packCheckExtra" style="font-size: 13px; font-weight: 800; color: #16a34a; margin-top: 2px;">0 UNEXPECTED</div>')

# Pack button to pass output to next agent:
text = text.replace('<button class="btn btn-primary" data-route="returns">Continue to Returns →</button>',
                    '<button class="btn btn-primary" onclick="window.passOutputToNextStage(\'pack\', \'returns\')">Pass Output to Agent 04 (Returns) →</button>')

text = text.replace('<button class="btn btn-primary" data-route="returns" style="width: 100%; margin-top: 16px;">\n                Complete Packing →\n              </button>',
                    '<button class="btn btn-primary" onclick="window.passOutputToNextStage(\'pack\', \'returns\')" style="width: 100%; margin-top: 16px;">\n                Pass Pack Output to Agent 04 (Returns) →\n              </button>')

# 13. Station 04 Returns:
text = text.replace('<div class="sec-step-num" style="background: #16a34a;">✓</div>',
                    '<div class="sec-step-num" style="background: #16a34a;">1</div>')
text = text.replace('<div class="sec-step-num" style="background: #16a34a;">✓</div>',
                    '<div class="sec-step-num" style="background: #16a34a;">2</div>')

text = text.replace('✓ Present', 'Present')
text = text.replace('⚠️ Discarded / Missing', 'Missing / Worn')

# Returns button to pass output to next agent:
text = text.replace('<button class="btn btn-primary" data-route="recovery">Continue to Recovery →</button>',
                    '<button class="btn btn-primary" onclick="window.passOutputToNextStage(\'returns\', \'recovery\')">Pass Output to Agent 05 (Recovery) →</button>')

text = text.replace('<button class="btn btn-primary btn-sm" data-route="recovery" style="margin-top: 10px;">Proceed to Recovery →</button>',
                    '<button class="btn btn-primary btn-sm" onclick="window.passOutputToNextStage(\'returns\', \'recovery\')" style="margin-top: 10px;">Pass Returns Output to Recovery →</button>')

# 14. Station 05 Recovery:
text = text.replace('✓ ACTIONABLE CLAIM', 'ACTIONABLE CLAIM')
text = text.replace('✓ CONTRADICTS AMAZON DEFECT CLAIM', 'CONTRADICTS AMAZON DEFECT CLAIM')
text = text.replace('✓ CONTRADICTED', 'CONTRADICTED')
text = text.replace('📋 Copy Dispute Letter', 'Copy Dispute Letter')
text = text.replace('📦 Copy JSON Payload', 'Copy JSON Payload')
text = text.replace('🚀 Submit to Amazon Seller Central', 'Submit to Amazon Seller Central')

# 15. Product Passport & Modals:
text = text.replace('<span id="passportHeaderPhotoPlaceholder" style="font-size: 22px;">📇</span>',
                    '<span id="passportHeaderPhotoPlaceholder" style="font-size: 22px;"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><line x1="15" y1="8" x2="17" y2="8"/><line x1="15" y1="12" x2="17" y2="12"/><line x1="7" y1="16" x2="17" y2="16"/></svg></span>')

text = text.replace('<button class="btn btn-secondary btn-sm" onclick="showToast(\'Displaying Lineage Graph Visualizer\')">View Graph 📊</button>',
                    '<button class="btn btn-secondary btn-sm" onclick="showToast(\'Displaying Lineage Graph Visualizer\')">View Lineage Graph</button>')

text = text.replace('<div class="modal-head-icon">📱</div>',
                    '<div class="modal-head-icon"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="5" y="2" width="14" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg></div>')

# Clean modal closes:
text = text.replace('✕', '&times;')

# Now, add Recovery dedicated image input and upstream chaining panels!
print("Text length after first pass:", len(text))
SRC.write_text(text, encoding="utf-8")
print("First pass saved.")
