import React from 'react';

/**
 * Welcome screen presented before conversations start.
 * Features hero greeting and high-converting suggested question cards.
 */
export default function WelcomeScreen({ onSelectPrompt }) {
    const suggestedPrompts = [
        {
            icon: '📐',
            title: 'Master Bedroom Dimensions',
            description: 'What are the master bedroom dimensions in the model houses?',
            query: 'What are the master bedroom dimensions?',
            tag: 'Dimensions',
        },
        {
            icon: '🏠',
            title: '2BHK Specifications',
            description: 'Detailed layout, balcony, kitchen & room specifications for 2BHK',
            query: 'What are the 2BHK specifications?',
            tag: '2BHK Layout',
        },
        {
            icon: '🏢',
            title: '3BHK Specifications',
            description: 'Room configurations, floor sizes & specifications for 3BHK',
            query: 'What are the 3BHK specifications?',
            tag: '3BHK Layout',
        },
        {
            icon: '⚖️',
            title: 'Compare 2BHK & 3BHK',
            description: 'Side-by-side room size, balcony & space comparison',
            query: 'Compare 2BHK and 3BHK.',
            tag: 'Comparison',
        },
        {
            icon: '🍳',
            title: 'Kitchen Specifications',
            description: 'Kitchen layout, utility area, counter specifications & orientation',
            query: 'What are the kitchen specifications?',
            tag: 'Kitchen & Utility',
        },
        {
            icon: '🚪',
            title: 'Entrance & Main Door Features',
            description: 'Grand main door measurements, veneer finish & digital locks',
            query: 'What are the entrance features?',
            tag: 'Entrance & Security',
        },
        {
            icon: '🔍',
            title: 'Live Inventory Search',
            description: 'Search available apartments by location and budget in Bangalore',
            query: 'Show me 2 BHK apartments in Bangalore below 80 lakhs',
            tag: 'Property Search',
        },
    ];

    return (
        <div className="welcome-screen animate-fade-in">
            <div className="welcome-hero">
                <div className="hero-pill-badge">
                    <span className="badge-sparkle">✦</span>
                    <span>AI-Powered Real Estate Assistant</span>
                </div>
                <h1 className="welcome-title">
                    Explore Properties & Architectural Specifications
                </h1>
                <p className="welcome-subtitle">
                    Ask questions about Casagrand Aquagrove model house scripts, floor plan dimensions,
                    materials, and live real-estate database inventory.
                </p>
            </div>

            <div className="suggested-section">
                <div className="section-label">
                    <span>Suggested Questions from Verified Documents</span>
                </div>
                <div className="prompts-grid">
                    {suggestedPrompts.map((p, idx) => (
                        <button
                            key={idx}
                            type="button"
                            className="prompt-card"
                            onClick={() => onSelectPrompt(p.query)}
                        >
                            <div className="prompt-top">
                                <span className="prompt-icon">{p.icon}</span>
                                <span className="prompt-tag">{p.tag}</span>
                            </div>
                            <h3 className="prompt-title">{p.title}</h3>
                            <p className="prompt-desc">{p.description}</p>
                            <div className="prompt-arrow">
                                <span>Ask this question</span>
                                <span className="arrow-icon">→</span>
                            </div>
                        </button>
                    ))}
                </div>
            </div>
        </div>
    );
}
