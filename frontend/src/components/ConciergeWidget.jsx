import React, { useState, useEffect, useRef } from 'react';
import PropertyDetailCard from './PropertyDetailCard';
import PropertyCardCarousel from './PropertyCardCarousel';

const QUICK_SUGGESTIONS = [
    'Show me 2BHK details',
    'What are the 3BHK bedroom dimensions?',
    'Give me 4BHK specifications',
    'Compare 2BHK and 3BHK',
    'Show bedroom images',
];

export default function ConciergeWidget({
    messages = [],
    onSend,
    isBusy = false,
    busyStatus = 'Analyzing query...',
    provider = 'gemini',
    setProvider,
    onSelectProperty,
    onSendBrochure,
    onStartOver,
    apiBaseUrl = '',
}) {
    const [isOpen, setIsOpen] = useState(true);
    const [inputValue, setInputValue] = useState('');
    const [currentTime, setCurrentTime] = useState('07:01 pm');
    const [previewImage, setPreviewImage] = useState(null);
    const messagesEndRef = useRef(null);
    const inputRef = useRef(null);

    // Live price timestamp formatting matching reference (e.g. "07:01 pm")
    useEffect(() => {
        const updateTime = () => {
            const now = new Date();
            setCurrentTime(now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }).toLowerCase());
        };
        updateTime();
        const interval = setInterval(updateTime, 60000);
        return () => clearInterval(interval);
    }, []);

    // Auto-scroll on new messages
    useEffect(() => {
        if (isOpen && messagesEndRef.current) {
            messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [messages, isBusy, isOpen]);

    const handleSubmit = (e) => {
        if (e) e.preventDefault();
        const text = inputValue.trim();
        if (!text || isBusy) return;
        onSend(text);
        setInputValue('');
    };

    const handleSuggestionClick = (suggestion) => {
        if (isBusy) return;
        onSend(suggestion);
    };

    const resolveImgUrl = (url) => {
        if (!url) return null;
        if (url.startsWith('http://') || url.startsWith('https://')) return url;
        return `${apiBaseUrl}${url.startsWith('/') ? '' : '/'}${url}`;
    };

    const hasMessages = messages.length > 0;

    return (
        <>
            {/* 1. Minimized Floating Launcher Button (Fixed at Bottom-Right corner) */}
            {!isOpen && (
                <button
                    type="button"
                    className="concierge-floating-launcher animate-fade-in"
                    onClick={() => setIsOpen(true)}
                    title="Open EstateAI Concierge"
                    aria-label="Open chat"
                >
                    <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                    </svg>
                </button>
            )}

            {/* 2. Top-Right Corner Floating Popup (465px x 685px, matching AWS Ask AWS reference) */}
            {isOpen && (
                <div className="concierge-card-container">
                    {/* Fixed Header */}
                    <header className="concierge-header">
                        <div className="concierge-header-left">
                            <span className="concierge-status-dot" title="AI Concierge Online" />
                            <div>
                                <h2 className="concierge-title">Concierge</h2>
                                <span className="concierge-subtitle">
                                    Website chat widget, simulated. English, Tamil, Tanglish
                                </span>
                            </div>
                        </div>

                        <div className="concierge-header-right">
                            {/* Discreet Provider Selector for AWS Bedrock */}
                            {setProvider && (
                                <select
                                    className="concierge-provider-select"
                                    value={provider}
                                    onChange={(e) => setProvider(e.target.value)}
                                    title="Active AI Engine"
                                >
                                    <option value="bedrock">Bedrock</option>
                                </select>
                            )}

                            <button
                                type="button"
                                className="concierge-start-over-btn"
                                onClick={onStartOver}
                                title="Start new conversation"
                            >
                                Start over
                            </button>

                            {/* Minimize Button */}
                            <button
                                type="button"
                                className="concierge-header-icon-btn"
                                onClick={() => setIsOpen(false)}
                                title="Minimize chat"
                                aria-label="Minimize"
                            >
                                —
                            </button>

                            {/* Close Button */}
                            <button
                                type="button"
                                className="concierge-header-icon-btn close-btn"
                                onClick={() => setIsOpen(false)}
                                title="Close chat"
                                aria-label="Close"
                            >
                                ✕
                            </button>
                        </div>
                    </header>

                    {/* Messages Conversation Stream (Vertically Scrollable) */}
                    <div className="concierge-messages-body">
                        {/* Clean Initial Welcome Screen */}
                        {!hasMessages && (
                            <div className="concierge-welcome-panel animate-fade-in">
                                <div className="concierge-welcome-avatar">
                                    <span className="logo-symbol">⌂</span>
                                </div>
                                <h3 className="concierge-welcome-title">Welcome to EstateAI Concierge</h3>
                                <p className="concierge-welcome-text">
                                    Ask me anything about property searches, BHK configurations, verified specifications, room dimensions, amenities, or pricing.
                                </p>

                                <div className="concierge-welcome-suggestions-box">
                                    <div className="concierge-welcome-label">Suggested questions:</div>
                                    <div className="concierge-welcome-chips-grid">
                                        {QUICK_SUGGESTIONS.map((suggestion, sIdx) => (
                                            <button
                                                key={sIdx}
                                                type="button"
                                                className="concierge-suggestion-chip"
                                                onClick={() => handleSuggestionClick(suggestion)}
                                                disabled={isBusy}
                                            >
                                                {suggestion}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Active Conversation Messages */}
                        {hasMessages && messages.map((m, idx) => {
                            const isUser = m.role === 'user';
                            const messageProps = m.properties || [];
                            const messageImages = m.images || [];

                            return (
                                <div
                                    key={idx}
                                    className={`concierge-msg-row ${isUser ? 'user-row' : 'assistant-row'}`}
                                >
                                    <div className={`concierge-bubble ${isUser ? 'user-bubble' : 'assistant-bubble'}`}>
                                        {m.content}
                                    </div>

                                    {/* One-card-at-a-time Property Carousel with Prev/Next controls */}
                                    {!isUser && messageProps.length > 0 && (
                                        <PropertyCardCarousel
                                            properties={messageProps}
                                            currentTime={currentTime}
                                            onSelectProperty={onSelectProperty}
                                            onSendBrochure={onSendBrochure}
                                            onImageClick={(imgData) => setPreviewImage(imgData)}
                                            resolveImgUrl={resolveImgUrl}
                                        />
                                    )}

                                    {/* Image Assets Carousel in message area */}
                                    {!isUser && messageImages.length > 0 && (
                                        <div className="concierge-images-track">
                                            {messageImages.map((img, iIdx) => (
                                                <div
                                                    key={iIdx}
                                                    className="concierge-image-thumb"
                                                    onClick={() => setPreviewImage({
                                                        url: resolveImgUrl(img.url),
                                                        title: img.property_name || img.filename,
                                                        category: img.category,
                                                    })}
                                                >
                                                    <img
                                                        src={resolveImgUrl(img.url)}
                                                        alt={img.filename}
                                                        loading="lazy"
                                                    />
                                                    <span className="concierge-image-label">
                                                        {img.category ? img.category.toUpperCase() : 'PHOTO'}
                                                    </span>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            );
                        })}

                        {/* Busy Typing Indicator */}
                        {isBusy && (
                            <div className="concierge-msg-row assistant-row">
                                <div className="concierge-bubble assistant-bubble concierge-typing-bubble">
                                    <span className="concierge-typing-dot" />
                                    <span className="concierge-typing-dot" />
                                    <span className="concierge-typing-dot" />
                                    <span className="concierge-typing-label">{busyStatus}</span>
                                </div>
                            </div>
                        )}

                        <div ref={messagesEndRef} />
                    </div>

                    {/* Quick Suggestion Chips */}
                    {hasMessages && (
                        <div className="concierge-suggestions-bar">
                            {QUICK_SUGGESTIONS.map((suggestion, sIdx) => (
                                <button
                                    key={sIdx}
                                    type="button"
                                    className="concierge-suggestion-chip"
                                    onClick={() => handleSuggestionClick(suggestion)}
                                    disabled={isBusy}
                                >
                                    {suggestion}
                                </button>
                            ))}
                        </div>
                    )}

                    {/* Fixed Bottom Input Bar */}
                    <form className="concierge-input-form" onSubmit={handleSubmit}>
                        <input
                            ref={inputRef}
                            type="text"
                            className="concierge-text-input"
                            placeholder="e.g. 3 BHK under 1.5 crore near OMR, east facing"
                            value={inputValue}
                            onChange={(e) => setInputValue(e.target.value)}
                            disabled={isBusy}
                        />
                        <button
                            type="submit"
                            className="concierge-send-btn"
                            disabled={!inputValue.trim() || isBusy}
                        >
                            Send
                        </button>
                    </form>
                </div>
            )}

            {/* Lightbox Image Preview Dialog */}
            {previewImage && (
                <div className="concierge-lightbox-overlay" onClick={() => setPreviewImage(null)}>
                    <div className="concierge-lightbox-dialog" onClick={(e) => e.stopPropagation()}>
                        <div className="concierge-lightbox-header">
                            <div>
                                <strong>{previewImage.title || 'Property Asset'}</strong>
                                {previewImage.category && (
                                    <span className="concierge-lightbox-badge">
                                        {previewImage.category.toUpperCase()}
                                    </span>
                                )}
                            </div>
                            <button
                                type="button"
                                className="concierge-lightbox-close"
                                onClick={() => setPreviewImage(null)}
                            >
                                ✕
                            </button>
                        </div>
                        {previewImage.url && (
                            <img
                                src={previewImage.url}
                                alt={previewImage.title || 'Property view'}
                                className="concierge-lightbox-img"
                            />
                        )}
                        {previewImage.specs && (
                            <div className="concierge-lightbox-specs">
                                {previewImage.specs}
                            </div>
                        )}
                    </div>
                </div>
            )}
        </>
    );
}
