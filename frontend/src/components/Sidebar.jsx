import React from 'react';

/**
 * Sidebar navigation component with conversation management,
 * new chat button, and active knowledge base status.
 */
export default function Sidebar({
    isOpen,
    onClose,
    onNewChat,
    conversations,
    activeChatId,
    onSelectChat,
    onDeleteChat,
}) {
    return (
        <>
            {/* Backdrop for mobile drawer */}
            {isOpen && <div className="sidebar-backdrop" onClick={onClose} />}

            <aside className={`app-sidebar ${isOpen ? 'open' : 'collapsed'}`}>
                <div className="sidebar-header">
                    <button
                        type="button"
                        className="new-chat-btn"
                        onClick={() => {
                            onNewChat();
                            if (window.innerWidth < 1024) onClose();
                        }}
                    >
                        <span className="plus-icon">+</span>
                        <span>New Conversation</span>
                    </button>
                </div>

                <div className="sidebar-section conversations-history">
                    <div className="sidebar-section-title">Recent Conversations</div>
                    <div className="conversation-list">
                        {conversations.length === 0 ? (
                            <div className="empty-history">
                                <span className="empty-icon">💬</span>
                                <small>No previous conversations</small>
                            </div>
                        ) : (
                            conversations.map((c) => (
                                <div
                                    key={c.id}
                                    className={`conversation-item ${
                                        c.id === activeChatId ? 'active' : ''
                                    }`}
                                    onClick={() => {
                                        onSelectChat(c.id);
                                        if (window.innerWidth < 1024) onClose();
                                    }}
                                >
                                    <span className="chat-item-icon">🗨️</span>
                                    <span className="chat-item-title" title={c.title}>
                                        {c.title || 'Property Conversation'}
                                    </span>
                                    <button
                                        type="button"
                                        className="delete-chat-btn"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            onDeleteChat(c.id);
                                        }}
                                        title="Delete conversation"
                                    >
                                        ×
                                    </button>
                                </div>
                            ))
                        )}
                    </div>
                </div>

                <div className="sidebar-section knowledge-base-section">
                    <div className="sidebar-section-title">
                        <span>Active Knowledge Base</span>
                        <span className="kb-badge">ChromaDB</span>
                    </div>
                    <div className="kb-document-card">
                        <div className="kb-doc-title">Casagrand Aquagrove</div>
                        <ul className="kb-doc-list">
                            <li>
                                <span className="doc-icon">📄</span>
                                <span className="doc-name" title="2BHK + 2T Model House Script - Casagrand Aquagrove.pdf">
                                    2BHK Model House Script
                                </span>
                            </li>
                            <li>
                                <span className="doc-icon">📄</span>
                                <span className="doc-name" title="3BHK + 3T Model House Script - Casagrand Aquagrove.pdf">
                                    3BHK Model House Script
                                </span>
                            </li>
                        </ul>
                        <div className="kb-pipeline-pill">
                            <span>Hybrid Search (Dense + BM25 + RRF)</span>
                        </div>
                    </div>
                </div>

                <div className="sidebar-footer">
                    <div className="user-profile-badge">
                        <div className="user-avatar-circle">Demo</div>
                        <div className="user-info">
                            <span className="user-name">Client Presentation</span>
                            <span className="user-role">Interactive RAG Demo</span>
                        </div>
                    </div>
                </div>
            </aside>
        </>
    );
}
