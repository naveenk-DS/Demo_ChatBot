import React, { useState } from 'react';
import MarkdownRenderer from './MarkdownRenderer';
import SourceCard from './SourceCard';

/**
 * Message Bubble component supporting Markdown, Copy-to-Clipboard,
 * Re-prompt/Regenerate, and Collapsible RAG Sources.
 */
export default function ChatMessage({ message, isLast, onRegenerate, isBusy }) {
    const [copied, setCopied] = useState(false);
    const isUser = message.role === 'user';

    const handleCopy = () => {
        if (!message.content) return;
        navigator.clipboard.writeText(message.content).then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        });
    };

    return (
        <div className={`chat-message-row ${isUser ? 'user-row' : 'assistant-row'}`}>
            <div className="avatar-container">
                {isUser ? (
                    <div className="user-avatar" title="You">
                        <span>You</span>
                    </div>
                ) : (
                    <div className="assistant-avatar" title="EstateAI Assistant">
                        <span className="logo-icon">⌂</span>
                    </div>
                )}
            </div>

            <div className="message-content-wrapper">
                <div className="message-header-info">
                    <span className="sender-name">{isUser ? 'You' : 'EstateAI Assistant'}</span>
                    {message.timestamp && (
                        <span className="message-time">{message.timestamp}</span>
                    )}
                </div>

                <div className={`message-bubble ${isUser ? 'user-bubble' : 'assistant-bubble'}`}>
                    {isUser ? (
                        <div className="user-text">{message.content}</div>
                    ) : (
                        <>
                            <MarkdownRenderer content={message.content} />
                            {message.sources && message.sources.length > 0 && (
                                <SourceCard sources={message.sources} />
                            )}
                        </>
                    )}
                </div>

                {/* Message action bar for Assistant */}
                {!isUser && (
                    <div className="message-actions">
                        <button
                            type="button"
                            className="action-btn"
                            onClick={handleCopy}
                            title="Copy response to clipboard"
                        >
                            {copied ? (
                                <>
                                    <span className="action-icon">✓</span>
                                    <span>Copied!</span>
                                </>
                            ) : (
                                <>
                                    <span className="action-icon">📋</span>
                                    <span>Copy</span>
                                </>
                            )}
                        </button>

                        {isLast && onRegenerate && (
                            <button
                                type="button"
                                className="action-btn"
                                onClick={onRegenerate}
                                disabled={isBusy}
                                title="Regenerate this response"
                            >
                                <span className="action-icon">🔄</span>
                                <span>Regenerate</span>
                            </button>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
