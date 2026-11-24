import React, { useRef, useEffect } from 'react';

/**
 * Modern floating chat composer input.
 * Supports Enter to send, Shift+Enter for multiline newline, and auto-focus.
 */
export default function ChatInput({ input, setInput, onSend, isBusy }) {
    const textareaRef = useRef(null);

    // Auto-resize textarea height
    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
            textareaRef.current.style.height = `${Math.min(
                textareaRef.current.scrollHeight,
                140
            )}px`;
        }
    }, [input]);

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (input.trim() && !isBusy) {
                onSend(e);
            }
        }
    };

    return (
        <div className="chat-composer-area">
            <form className="chat-composer-form" onSubmit={onSend}>
                <div className="composer-input-wrapper">
                    <textarea
                        ref={textareaRef}
                        rows={1}
                        className="composer-textarea"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Ask anything aboutspecifications or search properties now implementinng 2BHA and 3BHK doc only..."
                        disabled={isBusy}
                    />

                    {input.trim() && (
                        <button
                            type="button"
                            className="composer-clear-btn"
                            onClick={() => setInput('')}
                            title="Clear input"
                        >
                            ×
                        </button>
                    )}

                    <button
                        type="submit"
                        className="composer-send-btn"
                        disabled={!input.trim() || isBusy}
                        title="Send message (Enter)"
                    >
                        {isBusy ? (
                            <span className="send-spinner" />
                        ) : (
                            <span className="send-arrow">↑</span>
                        )}
                    </button>
                </div>
            </form>
            <div className="composer-footer-disclaimer">
                <span>
                    EstateAI provides answers from official model house scripts & property database. Please verify specifications before booking.
                </span>
            </div>
        </div>
    );
}
