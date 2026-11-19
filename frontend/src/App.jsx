import React, { useState, useEffect, useRef } from 'react';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import WelcomeScreen from './components/WelcomeScreen';
import ChatMessage from './components/ChatMessage';
import ChatInput from './components/ChatInput';
import PropertyResults from './components/PropertyResults';
import EnquiryModal from './components/EnquiryModal';

const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export function sanitizeFilters(filters) {
    if (!filters || typeof filters !== 'object') return undefined;
    const cleaned = {};
    for (const [key, value] of Object.entries(filters)) {
        if (value === '' || value === undefined || value === null) {
            continue;
        }
        if (['bhk', 'min_price', 'max_price'].includes(key)) {
            const num = Number(value);
            cleaned[key] = isNaN(num) ? value : num;
        } else {
            cleaned[key] = value;
        }
    }
    return Object.keys(cleaned).length > 0 ? cleaned : undefined;
}

const STORAGE_KEY = 'estateai_conversations_v1';

export default function App() {
    const [provider, setProvider] = useState(() => {
        return localStorage.getItem('estateai_provider') || 'ollama';
    });
    const [input, setInput] = useState('');
    const [messages, setMessages] = useState([]);
    const [properties, setProperties] = useState([]);
    const [busy, setBusy] = useState(false);
    const [busyStatus, setBusyStatus] = useState('Analyzing query...');
    const [selectedProperty, setSelectedProperty] = useState(null);
    const [notice, setNotice] = useState(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [sidebarOpen, setSidebarOpen] = useState(true);
    const [backendOnline, setBackendOnline] = useState(false);

    // Conversations history in localStorage
    const [conversations, setConversations] = useState(() => {
        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            return stored ? JSON.parse(stored) : [];
        } catch {
            return [];
        }
    });
    const [activeChatId, setActiveChatId] = useState(null);

    const [form, setForm] = useState({
        name: '',
        phone: '',
        message: 'I am interested in scheduling a site visit for this property.',
        consent: false,
    });

    const messagesEndRef = useRef(null);

    // Persist provider selection
    useEffect(() => {
        localStorage.setItem('estateai_provider', provider);
    }, [provider]);

    // Check backend health status
    useEffect(() => {
        let mounted = true;
        const checkHealth = async () => {
            try {
                const res = await fetch(`${API}/health`, { method: 'GET' });
                if (mounted) setBackendOnline(res.ok);
            } catch {
                if (mounted) setBackendOnline(false);
            }
        };
        checkHealth();
        const interval = setInterval(checkHealth, 30000);
        return () => {
            mounted = false;
            clearInterval(interval);
        };
    }, []);

    // Auto-scroll to bottom of conversation
    useEffect(() => {
        if (messages.length > 0) {
            messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }
    }, [messages, busy]);

    // Persist conversations
    useEffect(() => {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
        } catch (e) {
            console.error('Failed to save conversations to localStorage', e);
        }
    }, [conversations]);

    // Start a new conversation
    const handleNewChat = () => {
        setMessages([]);
        setProperties([]);
        setInput('');
        setActiveChatId(null);
        setNotice(null);
    };

    // Load an existing conversation from sidebar
    const handleSelectChat = (id) => {
        const found = conversations.find((c) => c.id === id);
        if (found) {
            setActiveChatId(found.id);
            setMessages(found.messages || []);
            setProperties(found.properties || []);
            setNotice(null);
        }
    };

    // Delete a conversation
    const handleDeleteChat = (id) => {
        const updated = conversations.filter((c) => c.id !== id);
        setConversations(updated);
        if (activeChatId === id) {
            handleNewChat();
        }
    };

    // Send a message (from form submit or suggested prompt card)
    const handleSend = async (textToSend) => {
        const content = (typeof textToSend === 'string' ? textToSend : input).trim();
        if (!content || busy) return;

        const timeString = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const userMsg = {
            role: 'user',
            content,
            timestamp: timeString,
        };

        const updatedMessages = [...messages, userMsg];
        setMessages(updatedMessages);
        setInput('');
        setBusy(true);
        setBusyStatus(provider === 'ollama' ? 'Querying local model (qwen2.5:7b) & vector store...' : 'Connecting to AI provider...');

        const historyPayload = messages.slice(-8).map((m) => ({
            role: m.role,
            content: m.content,
        }));

        try {
            const res = await fetch(`${API}/api/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: content,
                    history: historyPayload,
                    provider,
                }),
            });

            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.detail || 'Assistant request failed.');
            }

            const assistantMsg = {
                role: 'assistant',
                content: data.assistant_message || 'Search complete.',
                timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                sources: data.sources || [],
            };

            const finalMessages = [...updatedMessages, assistantMsg];
            setMessages(finalMessages);

            const receivedProperties = data.properties || [];
            setProperties(receivedProperties);

            // Update or create in conversation history
            const currentTitle = content.slice(0, 32) + (content.length > 32 ? '...' : '');
            if (activeChatId) {
                setConversations((prev) =>
                    prev.map((c) =>
                        c.id === activeChatId
                            ? { ...c, messages: finalMessages, properties: receivedProperties }
                            : c
                    )
                );
            } else {
                const newId = `chat_${Date.now()}`;
                setActiveChatId(newId);
                setConversations((prev) => [
                    {
                        id: newId,
                        title: currentTitle,
                        messages: finalMessages,
                        properties: receivedProperties,
                        createdAt: new Date().toISOString(),
                    },
                    ...prev.slice(0, 19),
                ]);
            }
        } catch (err) {
            const errorMsg = {
                role: 'assistant',
                content: `⚠️ **Error**: ${err.message}`,
                timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            };
            setMessages([...updatedMessages, errorMsg]);
        } finally {
            setBusy(false);
        }
    };

    // Regenerate last response
    const handleRegenerate = () => {
        const lastUserMsg = [...messages].reverse().find((m) => m.role === 'user');
        if (lastUserMsg) {
            // Remove the last assistant message and re-run
            const trimmed = messages.slice(0, -1);
            setMessages(trimmed);
            handleSend(lastUserMsg.content);
        }
    };

    // Submit Property Enquiry
    const handleEnquirySubmit = async (e) => {
        e.preventDefault();
        if (!form.consent || !selectedProperty) return;

        setIsSubmitting(true);
        try {
            const res = await fetch(`${API}/api/enquiries`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ...form,
                    property_id: selectedProperty?.property_id,
                }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Enquiry submission failed');

            setNotice({
                type: 'success',
                text: `✓ Site visit request submitted! Reference ID: ${data.enquiry_id}. Our specialist will contact you shortly.`,
            });
            setSelectedProperty(null);
            setForm({
                name: '',
                phone: '',
                message: 'I am interested in scheduling a site visit for this property.',
                consent: false,
            });
        } catch (err) {
            setNotice({
                type: 'error',
                text: `Submission Error: ${err.message}`,
            });
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="estate-app-container">
            {/* Top Navigation Header */}
            <Header
                provider={provider}
                setProvider={setProvider}
                onClearChat={handleNewChat}
                onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
                sidebarOpen={sidebarOpen}
                backendOnline={backendOnline}
            />

            {/* Notification Toast */}
            {notice && (
                <div className={`notification-toast ${notice.type} animate-slide-down`}>
                    <span>{notice.text}</span>
                    <button
                        type="button"
                        className="toast-close-btn"
                        onClick={() => setNotice(null)}
                    >
                        ×
                    </button>
                </div>
            )}

            {/* Main Application Shell with Sidebar and Dual-Pane Workspace */}
            <div className="app-workspace-layout">
                {/* Left Conversation & Knowledge Base Sidebar */}
                <Sidebar
                    isOpen={sidebarOpen}
                    onClose={() => setSidebarOpen(false)}
                    onNewChat={handleNewChat}
                    conversations={conversations}
                    activeChatId={activeChatId}
                    onSelectChat={handleSelectChat}
                    onDeleteChat={handleDeleteChat}
                />

                {/* Central Chat Panel */}
                <main className="chat-workspace-panel">
                    <div className="chat-thread-container">
                        {messages.length === 0 ? (
                            <WelcomeScreen onSelectPrompt={(q) => handleSend(q)} />
                        ) : (
                            <div className="messages-flow">
                                {messages.map((m, idx) => (
                                    <ChatMessage
                                        key={idx}
                                        message={m}
                                        isLast={idx === messages.length - 1 && m.role === 'assistant'}
                                        onRegenerate={handleRegenerate}
                                        isBusy={busy}
                                    />
                                ))}

                                {busy && (
                                    <div className="typing-indicator-row animate-fade-in">
                                        <div className="assistant-avatar">
                                            <span className="logo-icon">⌂</span>
                                        </div>
                                        <div className="typing-bubble">
                                            <div className="typing-dots">
                                                <span />
                                                <span />
                                                <span />
                                            </div>
                                            <span className="typing-status-text">{busyStatus}</span>
                                        </div>
                                    </div>
                                )}
                                <div ref={messagesEndRef} />
                            </div>
                        )}
                    </div>

                    {/* Chat Input Floating Composer */}
                    <ChatInput
                        input={input}
                        setInput={setInput}
                        onSend={(e) => {
                            e.preventDefault();
                            handleSend();
                        }}
                        isBusy={busy}
                    />
                </main>

                {/* Right Panel: Matching Property Inventory Showcase */}
                <aside className="property-showcase-aside">
                    <PropertyResults
                        properties={properties}
                        onSelectProperty={(prop) => {
                            setSelectedProperty(prop);
                            setNotice(null);
                        }}
                    />
                </aside>
            </div>

            {/* Property Contact & Enquiry Modal */}
            {selectedProperty && (
                <EnquiryModal
                    selectedProperty={selectedProperty}
                    form={form}
                    setForm={setForm}
                    onSubmit={handleEnquirySubmit}
                    onClose={() => setSelectedProperty(null)}
                    isSubmitting={isSubmitting}
                />
            )}
        </div>
    );
}
