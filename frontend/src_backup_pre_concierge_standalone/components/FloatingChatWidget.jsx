import React, { useState, useEffect, useRef } from 'react';
import MarkdownRenderer from './MarkdownRenderer';
import PropertyDetailCard from './PropertyDetailCard';

/**
 * Format numeric price to standard Indian currency display (e.g. ₹1.68 Cr or ₹85 L)
 */
function formatCrOrLakh(price) {
    if (!price) return 'Price on request';
    const num = Number(price);
    if (isNaN(num)) return price;
    if (num >= 10000000) {
        const cr = (num / 10000000).toFixed(2).replace(/\.00$/, '');
        return `₹${cr} Cr`;
    }
    if (num >= 100000) {
        const l = (num / 100000).toFixed(2).replace(/\.00$/, '');
        return `₹${l} L`;
    }
    return `₹${num.toLocaleString('en-IN')}`;
}

/**
 * Format rate per sq ft (e.g. ₹10,370/sq ft)
 */
function formatRatePerSqFt(price, sqft) {
    const numPrice = Number(price);
    const numSqft = Number(sqft);
    if (numPrice && numSqft && numSqft > 0) {
        const rate = Math.round(numPrice / numSqft);
        return `₹${rate.toLocaleString('en-IN')}/sq ft`;
    }
    return '';
}

/**
 * Suggestion prompts matching user's AWS Ask AWS reference screenshot
 */
const QUICK_SUGGESTIONS = [
    'Show me 2BHK details',
    'What are the 3BHK bedroom dimensions?',
    'Give me 4BHK specifications',
    'Compare 2BHK and 3BHK',
    'Show bedroom images',
];

export default function FloatingChatWidget({
    messages = [],
    properties = [],
    onSend,
    isBusy = false,
    busyStatus = 'Analyzing query...',
    onSelectProperty,
    onClearMessages,
    onNewChat,
    darkMode = false,
    setDarkMode,
    apiBaseUrl = '',
}) {
    const [isOpen, setIsOpen] = useState(false);
    const [inputValue, setInputValue] = useState('');
    const [currentTime, setCurrentTime] = useState('');
    const [menuOpen, setMenuOpen] = useState(false);
    const [isSearching, setIsSearching] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');
    const [previewImage, setPreviewImage] = useState(null);

    const messagesEndRef = useRef(null);
    const menuRef = useRef(null);
    const searchInputRef = useRef(null);

    // Current time for "Live price - as of hh:mm am/pm" badge
    useEffect(() => {
        const updateTime = () => {
            const now = new Date();
            setCurrentTime(now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }).toLowerCase());
        };
        updateTime();
        const interval = setInterval(updateTime, 60000);
        return () => clearInterval(interval);
    }, []);

    // Auto-scroll when messages update while widget is open (and not searching)
    useEffect(() => {
        if (isOpen && !isSearching) {
            messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }
    }, [messages, isBusy, isOpen, properties, isSearching]);

    // Close three-dot menu when clicking outside
    useEffect(() => {
        const handleClickOutside = (e) => {
            if (menuRef.current && !menuRef.current.contains(e.target)) {
                setMenuOpen(false);
            }
        };
        if (menuOpen) {
            document.addEventListener('mousedown', handleClickOutside);
        }
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [menuOpen]);

    // Auto-focus search input when search is opened
    useEffect(() => {
        if (isSearching) {
            setTimeout(() => searchInputRef.current?.focus(), 50);
        }
    }, [isSearching]);

    const handleSubmit = (e) => {
        e?.preventDefault();
        const trimmed = inputValue.trim();
        if (!trimmed || isBusy) return;
        onSend(trimmed);
        setInputValue('');
    };

    const handleChipClick = (suggestion) => {
        if (isBusy) return;
        onSend(suggestion);
    };

    const resolveImgUrl = (url) => {
        if (!url) return '';
        if (url.startsWith('http://') || url.startsWith('https://')) return url;
        const base = apiBaseUrl.replace(/\/+$/, '');
        const path = url.startsWith('/') ? url : `/${url}`;
        return base ? `${base}${path}` : path;
    };

    // Filter messages if search is active
    const filteredMessages = searchQuery.trim()
        ? messages.filter((m) =>
              (m.content || '').toLowerCase().includes(searchQuery.toLowerCase().trim())
          )
        : messages;

    // Helper to scroll horizontal carousel tracks smoothly
    const scrollCarousel = (trackId, direction) => {
        const track = document.getElementById(trackId);
        if (track) {
            const scrollAmount = direction === 'left' ? -260 : 260;
            track.scrollBy({ left: scrollAmount, behavior: 'smooth' });
        }
    };

    return (
        <div className="floating-chat-container">
            {/* Floating Chat Popup Window */}
            {isOpen && (
                <div
                    className="floating-chat-window animate-slide-up"
                    role="dialog"
                    aria-label="Property Assistant Chat"
                >
                    {/* Header */}
                    <div className="floating-chat-header">
                        <div className="floating-chat-header-title">
                            <span className="floating-online-dot" />
                            <div className="floating-header-info">
                                <span className="floating-header-name">Property Assistant</span>
                                <span className="floating-header-subtitle">AI Chat for Properties</span>
                            </div>
                        </div>

                        <div className="floating-header-actions">
                            {/* Three-Dot Menu Button */}
                            <div className="floating-menu-anchor" ref={menuRef}>
                                <button
                                    type="button"
                                    className={`floating-action-btn ${menuOpen ? 'menu-active' : ''}`}
                                    onClick={() => setMenuOpen(!menuOpen)}
                                    title="Options"
                                    aria-label="Conversation options"
                                >
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                                        <circle cx="12" cy="5" r="2.2" />
                                        <circle cx="12" cy="12" r="2.2" />
                                        <circle cx="12" cy="19" r="2.2" />
                                    </svg>
                                </button>

                                {/* Dropdown Menu */}
                                {menuOpen && (
                                    <div className="floating-menu-dropdown animate-fade-in">
                                        <button
                                            type="button"
                                            className="floating-menu-item"
                                            onClick={() => {
                                                setMenuOpen(false);
                                                setIsSearching(true);
                                            }}
                                        >
                                            <span className="menu-item-icon">🔍</span>
                                            <span>Search in conversation</span>
                                        </button>

                                        <button
                                            type="button"
                                            className="floating-menu-item"
                                            onClick={() => {
                                                setMenuOpen(false);
                                                if (onClearMessages) onClearMessages();
                                            }}
                                        >
                                            <span className="menu-item-icon">🗑️</span>
                                            <span>Clear conversation</span>
                                        </button>

                                        <button
                                            type="button"
                                            className="floating-menu-item"
                                            onClick={() => {
                                                setMenuOpen(false);
                                                if (onNewChat) onNewChat();
                                            }}
                                        >
                                            <span className="menu-item-icon">✨</span>
                                            <span>Start new conversation</span>
                                        </button>

                                        {setDarkMode && (
                                            <button
                                                type="button"
                                                className="floating-menu-item menu-divider-top"
                                                onClick={() => {
                                                    setDarkMode(!darkMode);
                                                    setMenuOpen(false);
                                                }}
                                            >
                                                <span className="menu-item-icon">{darkMode ? '☀️' : '🌙'}</span>
                                                <span>Website Dark Mode: {darkMode ? 'ON' : 'OFF'}</span>
                                            </button>
                                        )}
                                    </div>
                                )}
                            </div>

                            {/* Minimize Button */}
                            <button
                                type="button"
                                className="floating-action-btn"
                                onClick={() => setIsOpen(false)}
                                title="Minimize chat"
                                aria-label="Minimize"
                            >
                                —
                            </button>

                            {/* Close Button */}
                            <button
                                type="button"
                                className="floating-action-btn floating-close-btn"
                                onClick={() => setIsOpen(false)}
                                title="Close chat"
                                aria-label="Close"
                            >
                                ✕
                            </button>
                        </div>
                    </div>

                    {/* In-Chat Search Bar */}
                    {isSearching && (
                        <div className="floating-search-bar animate-slide-down">
                            <span className="floating-search-icon">🔍</span>
                            <input
                                ref={searchInputRef}
                                type="text"
                                className="floating-search-input"
                                placeholder="Search messages in conversation..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                            />
                            {searchQuery && (
                                <span className="floating-search-count">
                                    {filteredMessages.length} match{filteredMessages.length !== 1 ? 'es' : ''}
                                </span>
                            )}
                            <button
                                type="button"
                                className="floating-search-close"
                                onClick={() => {
                                    setIsSearching(false);
                                    setSearchQuery('');
                                }}
                                title="Close search"
                            >
                                ✕
                            </button>
                        </div>
                    )}

                    {/* Chat Body */}
                    <div className="floating-chat-body">
                        {/* Default friendly greeting if no messages yet */}
                        {messages.length === 0 ? (
                            <div className="floating-msg-row assistant-row">
                                <div className="floating-assistant-card">
                                    <p>
                                        Hello! I can help you find a home. Tell me what you are looking for in your own words: budget, area, or the kind of place you picture.
                                    </p>
                                </div>
                            </div>
                        ) : filteredMessages.length === 0 && searchQuery ? (
                            <div className="floating-search-empty">
                                <span>No messages found matching "{searchQuery}"</span>
                            </div>
                        ) : (
                            filteredMessages.map((m, idx) => {
                                const isAssistant = m.role === 'assistant';
                                const msgProperties = m.properties || (idx === filteredMessages.length - 1 ? properties : []);
                                const msgImages = m.images || [];

                                return (
                                    <div
                                        key={idx}
                                        className={`floating-msg-row ${isAssistant ? 'assistant-row' : 'user-row'}`}
                                    >
                                        {isAssistant ? (
                                            <div className="floating-assistant-card">
                                                <MarkdownRenderer content={m.content} />

                                                {/* Document Source Citations */}
                                                {m.sources && m.sources.length > 0 && (
                                                    <div className="floating-sources-area">
                                                        <span className="floating-sources-title">
                                                            📄 {m.sources.length} Verified Source{m.sources.length > 1 ? 's' : ''}:
                                                        </span>
                                                        <div className="floating-sources-tags">
                                                            {m.sources.map((s, sIdx) => (
                                                                <span key={sIdx} className="floating-source-tag">
                                                                    {s.source} (p.{s.page})
                                                                </span>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}

                                                {/* In-Chat Image Results Carousel (Directly inside chatbot conversation) */}
                                                {msgImages && msgImages.length > 0 && (
                                                    <div className="floating-carousel-container">
                                                        <div className="floating-carousel-header">
                                                            <span className="floating-carousel-title">
                                                                🖼️ Property Images ({msgImages.length})
                                                            </span>
                                                            {msgImages.length > 1 && (
                                                                <div className="floating-carousel-nav">
                                                                    <button
                                                                        type="button"
                                                                        className="carousel-nav-btn"
                                                                        onClick={() => scrollCarousel(`img-track-${idx}`, 'left')}
                                                                        aria-label="Previous image"
                                                                    >
                                                                        ‹
                                                                    </button>
                                                                    <button
                                                                        type="button"
                                                                        className="carousel-nav-btn"
                                                                        onClick={() => scrollCarousel(`img-track-${idx}`, 'right')}
                                                                        aria-label="Next image"
                                                                    >
                                                                        ›
                                                                    </button>
                                                                </div>
                                                            )}
                                                        </div>
                                                        <div className="floating-carousel-track" id={`img-track-${idx}`}>
                                                            {msgImages.map((img, imgIdx) => (
                                                                <div
                                                                    key={imgIdx}
                                                                    className="floating-image-card"
                                                                    onClick={() =>
                                                                        setPreviewImage({
                                                                            url: resolveImgUrl(img.url),
                                                                            title: img.filename,
                                                                            category: img.category,
                                                                            project: img.project_name,
                                                                        })
                                                                    }
                                                                    role="button"
                                                                    tabIndex={0}
                                                                    title="Click to expand larger image preview"
                                                                >
                                                                    <div className="floating-image-thumb-box">
                                                                        <img
                                                                            src={resolveImgUrl(img.url)}
                                                                            alt={img.filename || 'Property'}
                                                                            className="floating-image-thumb"
                                                                            loading="lazy"
                                                                        />
                                                                        <span className="floating-image-zoom-hint">🔍 Expand</span>
                                                                    </div>
                                                                    <div className="floating-image-caption">
                                                                        <span className="floating-image-badge">
                                                                            {(img.category || 'Asset').toUpperCase()}
                                                                        </span>
                                                                        <span className="floating-image-name">
                                                                            {img.filename}
                                                                        </span>
                                                                    </div>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}

                                                {/* In-Chat Matching Property Cards Carousel */}
                                                {msgProperties && msgProperties.length > 0 && (
                                                    <div className="floating-carousel-container">
                                                        <div className="floating-carousel-header">
                                                            <span className="floating-carousel-title">
                                                                🏡 Matching Homes ({msgProperties.length})
                                                            </span>
                                                            {msgProperties.length > 1 && (
                                                                <div className="floating-carousel-nav">
                                                                    <button
                                                                        type="button"
                                                                        className="carousel-nav-btn"
                                                                        onClick={() => scrollCarousel(`prop-track-${idx}`, 'left')}
                                                                        aria-label="Previous property"
                                                                    >
                                                                        ‹
                                                                    </button>
                                                                    <button
                                                                        type="button"
                                                                        className="carousel-nav-btn"
                                                                        onClick={() => scrollCarousel(`prop-track-${idx}`, 'right')}
                                                                        aria-label="Next property"
                                                                    >
                                                                        ›
                                                                    </button>
                                                                </div>
                                                            )}
                                                        </div>
                                                        <div className={`floating-carousel-track prop-ref-carousel-track ${msgProperties.length === 1 ? 'single-card' : ''}`} id={`prop-track-${idx}`}>
                                                            {msgProperties.map((prop, pIdx) => (
                                                                <PropertyDetailCard
                                                                    key={prop.property_id || pIdx}
                                                                    property={prop}
                                                                    index={pIdx}
                                                                    currentTime={currentTime}
                                                                    onSelectProperty={onSelectProperty}
                                                                    onSendBrochure={(p) => {
                                                                        if (onSelectProperty) onSelectProperty(p);
                                                                    }}
                                                                    onImageClick={(imgData) => setPreviewImage(imgData)}
                                                                    resolveImgUrl={resolveImgUrl}
                                                                />
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        ) : (
                                            <div className="floating-user-pill">
                                                {m.content}
                                            </div>
                                        )}
                                    </div>
                                );
                            })
                        )}

                        {/* Typing / Status Indicator */}
                        {isBusy && (
                            <div className="floating-typing-row">
                                <div className="floating-typing-dots">
                                    <span />
                                    <span />
                                    <span />
                                </div>
                                <span className="floating-typing-text">
                                    {busyStatus}
                                </span>
                            </div>
                        )}

                        {/* Suggestion Quick Chips */}
                        <div className="floating-suggestion-chips">
                            {QUICK_SUGGESTIONS.map((chip, idx) => (
                                <button
                                    key={idx}
                                    type="button"
                                    className="floating-chip-btn"
                                    onClick={() => handleChipClick(chip)}
                                    disabled={isBusy}
                                >
                                    {chip}
                                </button>
                            ))}
                        </div>

                        <div ref={messagesEndRef} />
                    </div>

                    {/* Chat Footer / Input Row */}
                    <div className="floating-chat-footer">
                        <form className="floating-input-form" onSubmit={handleSubmit}>
                            <input
                                type="text"
                                className="floating-input-field"
                                placeholder="e.g. 3 BHK under 1.5 crore near OMR, east facing"
                                value={inputValue}
                                onChange={(e) => setInputValue(e.target.value)}
                                disabled={isBusy}
                            />
                            <button
                                type="submit"
                                className="floating-send-btn"
                                disabled={isBusy || !inputValue.trim()}
                            >
                                Send
                            </button>
                        </form>
                    </div>
                </div>
            )}

            {/* Circular Floating Launcher Button Fixed at Bottom-Right */}
            <button
                type="button"
                className={`floating-chat-launcher ${isOpen ? 'active' : ''}`}
                onClick={() => setIsOpen(!isOpen)}
                aria-label={isOpen ? 'Collapse Property Assistant' : 'Open Property Assistant'}
                title={isOpen ? 'Collapse chat' : 'Chat with Property Assistant'}
            >
                <div className="launcher-icon">
                    {/* Speech bubble icon matching user's reference image */}
                    <svg
                        width="26"
                        height="26"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2.2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                    >
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                    </svg>
                </div>
            </button>

            {/* Larger Image Preview Modal (Lightbox) */}
            {previewImage && (
                <div
                    className="floating-lightbox-overlay animate-fade-in"
                    onClick={() => setPreviewImage(null)}
                    role="dialog"
                    aria-label="Image Preview"
                >
                    <div className="floating-lightbox-dialog" onClick={(e) => e.stopPropagation()}>
                        <div className="floating-lightbox-header">
                            <div className="floating-lightbox-meta">
                                <span className="floating-lightbox-cat">
                                    {(previewImage.category || 'Asset').toUpperCase()}
                                </span>
                                <span className="floating-lightbox-title">
                                    {previewImage.title || 'Image Preview'}
                                </span>
                            </div>
                            <button
                                type="button"
                                className="floating-lightbox-close"
                                onClick={() => setPreviewImage(null)}
                                title="Close preview"
                                aria-label="Close image preview"
                            >
                                ✕
                            </button>
                        </div>
                        <div className="floating-lightbox-body">
                            <img
                                src={previewImage.url}
                                alt={previewImage.title || 'Preview'}
                                className="floating-lightbox-img"
                            />
                        </div>
                        {previewImage.project && (
                            <div className="floating-lightbox-footer">
                                <span>Project: {previewImage.project}</span>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
