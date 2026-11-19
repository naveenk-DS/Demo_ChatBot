import React from 'react';
import PropertyCard from './PropertyCard';

/**
 * Matching property results showcase panel.
 * Displays retrieved Athena SQL inventory records alongside the conversational assistant.
 */
export default function PropertyResults({ properties, onSelectProperty, onClose }) {
    if (!properties || properties.length === 0) {
        return (
            <div className="property-results-panel empty-state">
                <div className="panel-header">
                    <div>
                        <h2 className="panel-title">Matching Inventory</h2>
                        <p className="panel-subtitle">Live verified inventory from database</p>
                    </div>
                </div>
                <div className="empty-results-box">
                    <div className="empty-building-icon">⌂</div>
                    <h3>Your matching properties will appear here</h3>
                    <p>
                        Ask the assistant for a preferred city, location, BHK configuration, or budget
                        (e.g., <em>"Show me 2 BHK apartments in Bangalore under 80 lakhs"</em>).
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="property-results-panel has-results">
            <div className="panel-header">
                <div>
                    <h2 className="panel-title">Matching Properties</h2>
                    <p className="panel-subtitle">Retrieved from connected property database</p>
                </div>
                <span className="results-count-pill">
                    {properties.length} Record{properties.length > 1 ? 's' : ''} Found
                </span>
            </div>

            <div className="property-grid-scroll">
                {properties.map((property, idx) => (
                    <PropertyCard
                        key={property.property_id || idx}
                        property={property}
                        onSelectForEnquiry={onSelectProperty}
                    />
                ))}
            </div>
        </div>
    );
}
