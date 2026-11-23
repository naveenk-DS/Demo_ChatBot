"""
Script to apply the Charcoal (#111827), Slate (#1F2937), Amber (#F59E0B),
Blue (#2563EB), Green (#10B981) modern theme and welcome panel styling
to frontend/src/style.css.
"""

from pathlib import Path

STYLE_PATH = Path("frontend/src/style.css")

NEW_THEME_CSS = """

/* ==========================================================================
   CONCIERGE WIDGET — MODERN CHARCOAL / SLATE / AMBER / BLUE THEME
   Palette:
   - Background: Dark Charcoal (#111827)
   - Chat panels/cards: Dark Slate (#1F2937)
   - Accent: Amber / Orange (#F59E0B)
   - Primary Blue: (#2563EB)
   - Status Green: (#10B981)
   - Text: White / Light Gray (#F9FAFB / #E5E7EB / #9CA3AF)
   - Borders: Subtle Dark-Gray (#374151)
   ========================================================================== */

.concierge-viewport {
    width: 100vw;
    height: 100vh;
    height: 100dvh;
    background: #111827;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    color: #F9FAFB;
}

.concierge-card-container {
    width: 100%;
    max-width: 880px;
    height: 100%;
    max-height: 94vh;
    background: #1F2937;
    border: 1px solid #374151;
    border-radius: 12px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-shadow: 0 24px 50px rgba(0, 0, 0, 0.65);
    position: relative;
}

@media (max-width: 880px) {
    .concierge-card-container {
        max-width: 100%;
        max-height: 100%;
        border-radius: 0;
        border: none;
    }
}

.concierge-header {
    height: 54px;
    background: #1F2937;
    border-bottom: 1px solid #374151;
    padding: 0 18px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-shrink: 0;
    z-index: 10;
}

.concierge-header-left {
    display: flex;
    align-items: center;
    gap: 10px;
    overflow: hidden;
}

.concierge-status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #10B981;
    box-shadow: 0 0 8px rgba(16, 185, 129, 0.7);
    flex-shrink: 0;
}

.concierge-title {
    font-size: 15px;
    font-weight: 700;
    color: #F9FAFB;
    letter-spacing: -0.2px;
    margin: 0;
    white-space: nowrap;
}

.concierge-subtitle {
    font-size: 11.5px;
    color: #9CA3AF;
    font-weight: 400;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.concierge-header-right {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
}

.concierge-provider-select {
    background: #111827;
    border: 1px solid #374151;
    color: #E5E7EB;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 11.5px;
    font-weight: 500;
    outline: none;
    cursor: pointer;
}

.concierge-provider-select:focus {
    border-color: #2563EB;
}

.concierge-mode-toggle-btn {
    background: transparent;
    border: 1px solid #374151;
    color: #9CA3AF;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 11.5px;
    cursor: pointer;
    transition: all 0.15s;
}

.concierge-mode-toggle-btn:hover {
    background: #374151;
    color: #F9FAFB;
}

.concierge-start-over-btn {
    background: #111827;
    border: 1px solid #374151;
    color: #E5E7EB;
    padding: 4px 14px;
    border-radius: 6px;
    font-size: 11.5px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s;
    white-space: nowrap;
}

.concierge-start-over-btn:hover {
    background: #374151;
    color: #F9FAFB;
    border-color: #F59E0B;
}

.concierge-messages-body {
    flex: 1;
    overflow-y: auto;
    padding: 20px 18px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    background: #111827;
}

.concierge-messages-body::-webkit-scrollbar {
    width: 6px;
}

.concierge-messages-body::-webkit-scrollbar-thumb {
    background: #374151;
    border-radius: 3px;
}

.concierge-messages-body::-webkit-scrollbar-thumb:hover {
    background: #4B5563;
}

/* ==========================================================================
   INITIAL WELCOME PANEL (Clean, Uncluttered, NO Sample Cards/Images)
   ========================================================================== */

.concierge-welcome-panel {
    background: #1F2937;
    border: 1px solid #374151;
    border-radius: 12px;
    padding: 32px 24px;
    text-align: center;
    margin: auto;
    max-width: 580px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
}

.concierge-welcome-avatar {
    width: 54px;
    height: 54px;
    border-radius: 50%;
    background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
    color: #FFFFFF;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 26px;
    margin: 0 auto 16px auto;
    box-shadow: 0 4px 14px rgba(37, 99, 235, 0.4);
}

.concierge-welcome-title {
    font-size: 18px;
    font-weight: 700;
    color: #F9FAFB;
    margin: 0 0 8px 0;
}

.concierge-welcome-text {
    font-size: 13.5px;
    color: #9CA3AF;
    line-height: 1.55;
    margin: 0 auto 24px auto;
    max-width: 460px;
}

.concierge-welcome-suggestions-box {
    display: flex;
    flex-direction: column;
    gap: 10px;
    align-items: center;
}

.concierge-welcome-label {
    font-size: 11px;
    font-weight: 600;
    color: #D1D5DB;
    text-transform: uppercase;
    letter-spacing: 0.6px;
}

.concierge-welcome-chips-grid {
    display: flex;
    flex-direction: column;
    gap: 8px;
    width: 100%;
    max-width: 440px;
}

.concierge-msg-row {
    display: flex;
    flex-direction: column;
    width: 100%;
    animation: fadeInMsg 0.2s ease;
}

.concierge-msg-row.user-row {
    align-items: flex-end;
}

.concierge-msg-row.assistant-row {
    align-items: flex-start;
}

.concierge-bubble.user-bubble {
    background: #2563EB;
    color: #FFFFFF;
    border-radius: 18px 18px 4px 18px;
    padding: 10px 16px;
    font-size: 13.5px;
    line-height: 1.45;
    max-width: 82%;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
}

.concierge-bubble.assistant-bubble {
    background: #1F2937;
    border: 1px solid #374151;
    color: #F3F4F6;
    border-radius: 4px 18px 18px 18px;
    padding: 12px 18px;
    font-size: 13.5px;
    line-height: 1.5;
    max-width: 94%;
}

.concierge-cards-track {
    display: flex;
    gap: 14px;
    overflow-x: auto;
    padding: 12px 2px 16px 2px;
    width: 100%;
    scroll-snap-type: x mandatory;
    scrollbar-width: thin;
}

.concierge-cards-track::-webkit-scrollbar {
    height: 6px;
}

.concierge-cards-track::-webkit-scrollbar-thumb {
    background: #374151;
    border-radius: 3px;
}

.concierge-cards-track::-webkit-scrollbar-thumb:hover {
    background: #2563EB;
}

.concierge-images-track {
    display: flex;
    gap: 10px;
    overflow-x: auto;
    padding: 10px 2px;
    width: 100%;
}

.concierge-image-thumb {
    flex-shrink: 0;
    width: 180px;
    height: 120px;
    border-radius: 8px;
    overflow: hidden;
    position: relative;
    border: 1px solid #374151;
    cursor: pointer;
    background: #111827;
}

.concierge-image-thumb img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    transition: transform 0.2s;
}

.concierge-image-thumb:hover img {
    transform: scale(1.05);
}

.concierge-image-label {
    position: absolute;
    bottom: 4px;
    left: 4px;
    background: rgba(17, 24, 39, 0.85);
    color: #F59E0B;
    font-size: 9px;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 4px;
    letter-spacing: 0.5px;
}

.concierge-typing-bubble {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 10px 14px;
}

.concierge-typing-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #F59E0B;
    animation: bounce 1.4s infinite ease-in-out both;
}

.concierge-typing-dot:nth-child(1) { animation-delay: -0.32s; }
.concierge-typing-dot:nth-child(2) { animation-delay: -0.16s; }

.concierge-typing-label {
    font-size: 11px;
    color: #9CA3AF;
    margin-left: 6px;
}

.concierge-suggestions-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    padding: 8px 18px 12px 18px;
    background: #1F2937;
    flex-shrink: 0;
    border-top: 1px solid #374151;
}

.concierge-suggestion-chip {
    background: #111827;
    border: 1px solid #374151;
    color: #E5E7EB;
    font-size: 12.5px;
    font-weight: 500;
    padding: 7px 14px;
    border-radius: 20px;
    cursor: pointer;
    transition: all 0.15s ease;
    white-space: nowrap;
    text-align: center;
}

.concierge-suggestion-chip:hover:not(:disabled) {
    background: #374151;
    border-color: #F59E0B;
    color: #F59E0B;
    box-shadow: 0 0 10px rgba(245, 158, 11, 0.25);
}

.concierge-suggestion-chip:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.concierge-input-form {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 18px;
    background: #1F2937;
    border-top: 1px solid #374151;
    flex-shrink: 0;
}

.concierge-text-input {
    flex: 1;
    background: #111827;
    border: 1px solid #374151;
    border-radius: 8px;
    padding: 11px 14px;
    font-size: 13px;
    color: #F9FAFB;
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
}

.concierge-text-input:focus {
    border-color: #2563EB;
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.25);
}

.concierge-text-input::placeholder {
    color: #6B7280;
}

.concierge-send-btn {
    background: #2563EB;
    color: #FFFFFF;
    font-size: 13px;
    font-weight: 600;
    border: none;
    border-radius: 8px;
    padding: 11px 22px;
    cursor: pointer;
    transition: all 0.15s;
    letter-spacing: 0.3px;
}

.concierge-send-btn:hover:not(:disabled) {
    background: #1D4ED8;
    box-shadow: 0 2px 10px rgba(37, 99, 235, 0.4);
}

.concierge-send-btn:disabled {
    background: #374151;
    color: #6B7280;
    cursor: not-allowed;
}

.concierge-lightbox-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.85);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 20px;
}

.concierge-lightbox-dialog {
    background: #1F2937;
    border: 1px solid #374151;
    border-radius: 12px;
    max-width: 90vw;
    max-height: 85vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.8);
}

.concierge-lightbox-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 18px;
    border-bottom: 1px solid #374151;
    color: #F9FAFB;
}

.concierge-lightbox-badge {
    margin-left: 8px;
    background: rgba(37, 99, 235, 0.15);
    color: #60A5FA;
    border: 1px solid #2563EB;
    font-size: 10px;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 4px;
}

.concierge-lightbox-close {
    background: transparent;
    border: none;
    color: #9CA3AF;
    font-size: 18px;
    cursor: pointer;
}

.concierge-lightbox-close:hover {
    color: #F9FAFB;
}

.concierge-lightbox-img {
    max-width: 100%;
    max-height: calc(85vh - 60px);
    object-fit: contain;
}

/* ==========================================================================
   PROPERTY DETAIL CARD — SLATE/CHARCOAL/AMBER/BLUE MODERN THEME
   ========================================================================== */

.prop-detail-card-ref {
    flex: 0 0 320px;
    min-width: 320px;
    max-width: 320px;
    scroll-snap-align: start;
    background: #1F2937;
    border: 1px solid #374151;
    border-radius: 10px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.4);
    transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
    padding-bottom: 14px;
}

.prop-detail-card-ref:hover {
    transform: translateY(-2px);
    border-color: #2563EB;
    box-shadow: 0 12px 30px rgba(37, 99, 235, 0.2), 0 10px 25px rgba(0, 0, 0, 0.6);
}

.prop-ref-media-box {
    width: 100%;
    height: 152px;
    background: #111827;
    overflow: hidden;
    position: relative;
    cursor: pointer;
}

.prop-ref-real-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
    transition: transform 0.25s ease;
}

.prop-ref-media-box:hover .prop-ref-real-img {
    transform: scale(1.04);
}

.prop-ref-disclaimer {
    padding: 8px 14px 4px 14px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 11px;
    line-height: 1.4;
    color: #9CA3AF;
}

.prop-ref-title {
    padding: 4px 14px 0 14px;
    font-size: 15px;
    font-weight: 700;
    color: #F9FAFB;
    line-height: 1.35;
    margin: 0;
}

.prop-ref-price-row {
    padding: 6px 14px 0 14px;
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 8px;
}

.prop-ref-price {
    font-size: 19px;
    font-weight: 800;
    color: #F59E0B;
    letter-spacing: -0.3px;
}

.prop-ref-rate {
    font-size: 11.5px;
    font-weight: 600;
    color: #9CA3AF;
}

.prop-ref-live-badge {
    margin: 6px 14px 0 14px;
    display: inline-flex;
    align-items: center;
    padding: 3px 8px;
    background: rgba(16, 185, 129, 0.1);
    border: 1px solid rgba(16, 185, 129, 0.35);
    border-radius: 4px;
    font-size: 10.5px;
    font-weight: 600;
    color: #10B981;
    font-family: ui-monospace, SFMono-Regular, monospace;
    width: fit-content;
}

.prop-ref-specs-line {
    padding: 8px 14px 0 14px;
    font-size: 11.5px;
    color: #D1D5DB;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    line-height: 1.4;
}

.prop-ref-specs-line span:not(:last-child)::after {
    content: "·";
    margin-left: 8px;
    color: #6B7280;
}

.prop-ref-availability-line {
    padding: 4px 14px 0 14px;
    font-size: 11.5px;
    font-weight: 600;
    color: #9CA3AF;
}

.prop-ref-description {
    padding: 8px 14px 0 14px;
    font-size: 12px;
    line-height: 1.5;
    color: #D1D5DB;
    margin: 0;
}

.prop-ref-amenities {
    padding: 6px 14px 0 14px;
    font-size: 11px;
    color: #9CA3AF;
}

.prop-ref-tags-container {
    padding: 8px 14px 0 14px;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}

.prop-ref-tag-pill {
    background: #111827;
    border: 1px solid #374151;
    color: #60A5FA;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 8px;
    border-radius: 4px;
    letter-spacing: 0.2px;
}

.prop-ref-actions-row {
    padding: 12px 14px 0 14px;
    display: flex;
    gap: 8px;
}

.prop-ref-btn {
    flex: 1;
    padding: 8px 0;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    text-align: center;
    transition: all 0.15s ease;
}

.prop-ref-btn.site-visit-btn {
    background: #2563EB;
    border: 1px solid #2563EB;
    color: #FFFFFF;
}

.prop-ref-btn.site-visit-btn:hover {
    background: #1D4ED8;
    border-color: #1D4ED8;
    box-shadow: 0 2px 8px rgba(37, 99, 235, 0.4);
}

.prop-ref-btn.brochure-btn {
    background: #111827;
    border: 1px solid #374151;
    color: #E5E7EB;
}

.prop-ref-btn.brochure-btn:hover {
    background: #374151;
    border-color: #F59E0B;
    color: #F59E0B;
}

/* Expandable Details Accordion */
.prop-ref-details-section {
    margin: 10px 14px 0 14px;
    border-top: 1px solid #374151;
    padding-top: 8px;
}

.prop-ref-details-toggle {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    background: #111827;
    border: 1px solid #374151;
    border-radius: 6px;
    color: #F59E0B;
    font-size: 11.5px;
    font-weight: 600;
    padding: 6px 10px;
    cursor: pointer;
    text-align: left;
    transition: background 0.15s ease, border-color 0.15s ease;
}

.prop-ref-details-toggle:hover {
    background: #2D3748;
    border-color: #F59E0B;
}

.prop-ref-details-count {
    font-size: 10px;
    font-weight: 400;
    opacity: 0.8;
}

.prop-ref-details-list {
    list-style: none;
    margin: 8px 0 0 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
    max-height: 220px;
    overflow-y: auto;
}

.prop-ref-details-list::-webkit-scrollbar {
    width: 3px;
}

.prop-ref-details-list::-webkit-scrollbar-thumb {
    background: #F59E0B;
    border-radius: 2px;
}

.prop-ref-details-item {
    font-size: 11.5px;
    color: #E5E7EB;
    background: #111827;
    border-left: 2px solid #F59E0B;
    padding: 4px 8px;
    border-radius: 0 4px 4px 0;
    line-height: 1.4;
}
"""

def update_css():
    with open(STYLE_PATH, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    # Find where CONCIERGE WIDGET starts
    marker = "CONCIERGE WIDGET"
    idx = content.find(marker)
    if idx != -1:
        # Seek back to comment start /* =====
        comment_start = content.rfind("/* =", 0, idx)
        if comment_start != -1:
            base_content = content[:comment_start].rstrip()
        else:
            base_content = content[:idx].rstrip()
    else:
        base_content = content.rstrip()

    full_updated = base_content + "\n" + NEW_THEME_CSS

    with open(STYLE_PATH, "w", encoding="utf-8") as f:
        f.write(full_updated)

    print("style.css successfully updated with Charcoal/Slate/Amber/Blue theme.")

if __name__ == "__main__":
    update_css()

