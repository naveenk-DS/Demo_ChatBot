import React from 'react';

/**
 * Top Application Header.
 * Features branding, connection status pill, LLM provider selector, and action buttons.
 */
export default function Header({
    provider,
    setProvider,
    onClearChat,
    onToggleSidebar,
    sidebarOpen,
    backendOnline,
    apiBaseUrl = '',
    darkMode = false,
    setDarkMode,
}) {
    return (
        <header className="app-header">
            <div className="header-left">
                <button
                    type="button"
                    className="sidebar-toggle-btn"
                    onClick={onToggleSidebar}
                    aria-label="Toggle Sidebar"
                    title={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
                >
                    <span className="hamburger-icon">☰</span>
                </button>

                <div className="brand-logo-area">
                    <div className="brand-icon">⌂</div>
                    <div className="brand-text">
                        <span className="brand-name">EstateAI</span>
                        <span className="brand-sub">Real Estate Intelligence</span>
                    </div>
                </div>

                <div
                    className="status-pill-indicator"
                    title={backendOnline ? `Connected to ${apiBaseUrl || 'backend'}` : `Trying to reach ${apiBaseUrl || 'backend'}...`}
                >
                    <span
                        className={`status-dot ${backendOnline ? 'online' : 'checking'}`}
                    />
                    <span className="status-label">
                        {backendOnline ? 'System Online' : 'Connecting...'}
                    </span>
                </div>
            </div>

            <div className="header-right">
                <div className="provider-selector-wrapper">
                    <label htmlFor="llm-provider-select" className="provider-label">
                        LLM Provider:
                    </label>
                    <div className="custom-select-container">
                        <select
                            id="llm-provider-select"
                            className="provider-select"
                            value={provider}
                            onChange={(e) => setProvider(e.target.value)}
                        >
                            <option value="ollama">Ollama (Local Private AI)</option>
                            <option value="openai">OpenAI (GPT-4.1-mini)</option>
                            <option value="gemini">Google Gemini (3.5 Flash-Lite)</option>
                        </select>
                    </div>

                    {provider === 'ollama' && (
                        <div className="local-ai-badge" title="Running 100% on local machine with nomic-embed-text & qwen2.5:7b">
                            <span className="lock-icon">🔒</span>
                            <span>Local AI · Private</span>
                        </div>
                    )}
                </div>

                {setDarkMode && (
                    <button
                        type="button"
                        className={`header-action-btn theme-toggle-btn ${darkMode ? 'dark-active' : ''}`}
                        onClick={() => setDarkMode(!darkMode)}
                        title={darkMode ? 'Switch website to light background' : 'Switch website to dark background'}
                    >
                        <span className="action-icon">{darkMode ? '☀️' : '🌙'}</span>
                        <span className="btn-text">{darkMode ? 'Light' : 'Dark'}</span>
                    </button>
                )}

                <button
                    type="button"
                    className="header-action-btn clear-btn"
                    onClick={onClearChat}
                    title="Clear current conversation"
                >
                    <span className="action-icon">🗑️</span>
                    <span className="btn-text">Clear Chat</span>
                </button>
            </div>
        </header>
    );
}
