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
                                    className={`conversation-item ${c.id === activeChatId ? 'active' : ''
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

                <div className="sidebar-footer">
                    <div className="user-profile-badge">
                        <div className="user-avatar-circle">Demo</div>
                        <div className="user-info">
                            <span className="user-name">KP sir Presentation</span>
                            <span className="user-role">Interactive Demo To user</span>
                        </div>
                    </div>
                </div>
            </aside>
        </>
    );
}
