import React, { useState, useEffect, useRef } from 'react';
import PropertyDetailCard from './PropertyDetailCard';

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
    onToggleViewMode,
    isStandalone = false,
}) {
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
        if (messagesEndRef.current) {
            messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [messages, isBusy]);

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
        <div className="concierge-viewport">
            <div className="concierge-card-container">
                {/* 1. Header with Modern Slate/Blue Theme */}
                <header className="concierge-header">
                    <div className="concierge-header-left">
                        <span className="concierge-status-dot" title="AI Concierge Active" />
                        <h2 className="concierge-title">Concierge</h2>
                        <span className="concierge-subtitle">
                            Website chat widget, simulated. English, Tamil, Tanglish
                        </span>
                    </div>

                    <div className="concierge-header-right">
                        {/* Discreet Provider Selector for Client/CTO Demo */}
                        {setProvider && (
                            <select
                                className="concierge-provider-select"
                                value={provider}
                                onChange={(e) => setProvider(e.target.value)}
                                title="Select LLM Engine for Demo"
                            >
                                <option value="gemini">Google Gemini</option>
                                <option value="openai">OpenAI (GPT-4.1)</option>
                                <option value="ollama">Ollama (Private)</option>
                            </select>
                        )}

                        {onToggleViewMode && (
                            <button
                                type="button"
                                className="concierge-mode-toggle-btn"
                                onClick={onToggleViewMode}
                                title="Switch between Full Dashboard and Concierge Widget"
                            >
                                {isStandalone ? 'Dashboard View' : 'Full Screen'}
                            </button>
                        )}

                        <button
                            type="button"
                            className="concierge-start-over-btn"
                            onClick={onStartOver}
                        >
                            Start over
                        </button>
                    </div>
                </header>

                {/* 2. Messages Conversation Stream */}
                <div className="concierge-messages-body">
                    {/* Clean Initial Welcome Screen (NO sample cards or images) */}
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

                                {/* Property Cards Carousel ONLY when requested by user */}
                                {!isUser && messageProps.length > 0 && (
                                    <div className="concierge-cards-track">
                                        {messageProps.map((prop, pIdx) => (
                                            <PropertyDetailCard
                                                key={prop.property_id || pIdx}
                                                property={prop}
                                                index={pIdx}
                                                currentTime={currentTime}
                                                onSelectProperty={onSelectProperty}
                                                onSendBrochure={onSendBrochure}
                                                onImageClick={(imgData) => setPreviewImage(imgData)}
                                                resolveImgUrl={resolveImgUrl}
                                            />
                                        ))}
                                    </div>
                                )}

                                {/* Image Assets Carousel ONLY when images requested */}
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

                {/* 3. Quick Suggestions Rounded Chips (visible during conversation as well) */}
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

                {/* 4. Bottom Input Bar Fixed at Bottom */}
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
                        <img
                            src={previewImage.url}
                            alt={previewImage.title || 'Property view'}
                            className="concierge-lightbox-img"
                        />
                    </div>
                </div>
            )}
        </div>
    );
}
