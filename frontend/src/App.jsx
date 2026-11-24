import React, { useState, useEffect } from 'react';
import EnquiryModal from './components/EnquiryModal';
import ConciergeWidget from './components/ConciergeWidget';

export function getApiBaseUrl() {
    // 1. Check Vite build-time environment variables
    const envUrl = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL;
    if (envUrl && typeof envUrl === 'string' && envUrl.trim()) {
        return envUrl.trim().replace(/\/+$/, '');
    }
    // 2. Check localStorage runtime override (useful for deployed client demo)
    if (typeof window !== 'undefined') {
        const stored = localStorage.getItem('estateai_api_url');
        if (stored && stored.trim()) {
            return stored.trim().replace(/\/+$/, '');
        }
        // 3. Localhost development fallback
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            return 'http://localhost:8000';
        }
    }
    // 4. Same-origin fallback for production reverse proxy / single domain
    return '';
}

const API = getApiBaseUrl();
const STORAGE_KEY = 'estateai_conversations_v1';

export default function App() {
    const [provider, setProvider] = useState(() => {
        return localStorage.getItem('estateai_provider') || 'bedrock';
    });
    const [messages, setMessages] = useState([]);
    const [busy, setBusy] = useState(false);
    const [busyStatus, setBusyStatus] = useState('Analyzing query...');
    const [selectedProperty, setSelectedProperty] = useState(null);
    const [notice, setNotice] = useState(null);
    const [isSubmitting, setIsSubmitting] = useState(false);

    // Form state for Site Visit Booking & Enquiry
    const [form, setForm] = useState({
        name: '',
        phone: '',
        message: 'I am interested in scheduling a site visit for this property.',
        consent: false,
    });

    // Persist provider selection
    useEffect(() => {
        try {
            localStorage.setItem('estateai_provider', provider);
        } catch {
            // Ignore storage errors
        }
    }, [provider]);

    // Start a new conversation
    const handleNewChat = () => {
        setMessages([]);
        setNotice(null);
    };

    // Send a message to backend /api/chat
    const handleSend = async (contentToSend) => {
        const content = (contentToSend || '').trim();
        if (!content || busy) return;

        const timeString = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const userMsg = {
            role: 'user',
            content,
            timestamp: timeString,
        };

        const updatedMessages = [...messages, userMsg];
        setMessages(updatedMessages);
        setBusy(true);

        const providerLabel = provider === 'bedrock' ? 'Amazon Bedrock' : (provider === 'gemini' ? 'Google Gemini' : 'Amazon Bedrock');
        setBusyStatus(`Connecting to ${providerLabel}...`);

        const t1 = setTimeout(() => {
            setBusyStatus('Retrieving verified property documents...');
        }, 2200);
        const t2 = setTimeout(() => {
            setBusyStatus(`Synthesizing response with ${providerLabel}...`);
        }, 5500);

        const historyPayload = messages.slice(-8).map((m) => ({
            role: m.role,
            content: m.content,
        }));

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 45000);

        try {
            const res = await fetch(`${API}/api/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: content,
                    history: historyPayload,
                    provider,
                }),
                signal: controller.signal,
            });

            clearTimeout(timeoutId);
            clearTimeout(t1);
            clearTimeout(t2);

            let data;
            const contentType = res.headers.get('content-type') || '';
            if (contentType.includes('application/json')) {
                data = await res.json();
            } else {
                const text = await res.text();
                data = { detail: text || `Server returned HTTP ${res.status}` };
            }

            if (!res.ok) {
                throw new Error(data.detail || `Server error (HTTP ${res.status})`);
            }

            const receivedProperties = data.properties || [];
            const receivedImages = data.images || [];
            const receivedImageFilter = data.image_filter || null;

            const assistantMsg = {
                role: 'assistant',
                content: data.assistant_message || 'Here are the details from the property documents.',
                timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                sources: data.sources || [],
                properties: receivedProperties,
                images: receivedImages,
                imageFilter: receivedImageFilter,
            };

            setMessages([...updatedMessages, assistantMsg]);
        } catch (err) {
            clearTimeout(timeoutId);
            clearTimeout(t1);
            clearTimeout(t2);

            let errorText = err.message || 'Unknown network error';
            if (err.name === 'AbortError') {
                errorText = 'Request timed out after 45 seconds. Please try again.';
            } else if (errorText.includes('Failed to fetch') || errorText.includes('NetworkError')) {
                const targetHost = API || window.location.origin;
                errorText = `Unable to connect to backend server at ${targetHost}. Please verify the server is running on port 8000.`;
            }

            const errorMsg = {
                role: 'assistant',
                content: `⚠️ Connection Error: ${errorText}`,
                timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            };
            setMessages([...updatedMessages, errorMsg]);
        } finally {
            clearTimeout(timeoutId);
            clearTimeout(t1);
            clearTimeout(t2);
            setBusy(false);
        }
    };

    // Submit Property Enquiry / Site Visit
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
        <div className="standalone-concierge-root">
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

            {/* Standalone Compact Concierge Chatbot Interface */}
            <ConciergeWidget
                messages={messages}
                onSend={handleSend}
                isBusy={busy}
                busyStatus={busyStatus}
                provider={provider}
                setProvider={setProvider}
                onSelectProperty={(prop) => {
                    setSelectedProperty(prop);
                    setNotice(null);
                }}
                onSendBrochure={(prop) => {
                    setSelectedProperty(prop);
                    setForm((prev) => ({
                        ...prev,
                        message: `Please send the official project brochure and pricing sheet for ${prop.property_name || 'this property'}.`,
                    }));
                }}
                onStartOver={handleNewChat}
                apiBaseUrl={API}
            />
        </div>
    );
}
