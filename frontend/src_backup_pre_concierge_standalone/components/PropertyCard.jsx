import React from 'react';

/**
 * Formats numeric price into standard Indian Rupee format (e.g. ₹85,00,000 or ₹1.25 Cr)
 */
function formatPrice(price) {
    if (!price) return 'Price on request';
    const num = Number(price);
    if (isNaN(num)) return price;
    return `₹${num.toLocaleString('en-IN')}`;
}

export default function PropertyCard({ property, onSelectForEnquiry }) {
    return (
        <article className="property-card animate-fade-in">
            <div className="property-image-container">
                {property.image_url ? (
                    <img
                        src={property.image_url}
                        alt={property.property_type || 'Property'}
                        className="property-img"
                        loading="lazy"
                    />
                ) : (
                    <div className="property-placeholder">
                        <span className="placeholder-icon">🏢</span>
                        <span className="placeholder-text">Architectural Rendering</span>
                    </div>
                )}
                <div className="property-badges-overlay">
                    {property.bhk && (
                        <span className="badge-pill bhk-badge">
                            {property.bhk} BHK
                        </span>
                    )}
                    {property.property_type && (
                        <span className="badge-pill type-badge">
                            {property.property_type}
                        </span>
                    )}
                    {property.property_status && (
                        <span className="badge-pill status-badge">
                            {property.property_status}
                        </span>
                    )}
                </div>
            </div>

            <div className="property-body">
                <div className="property-price">
                    {formatPrice(property.price)}
                </div>

                <div className="property-location">
                    <span className="location-icon">📍</span>
                    <span>
                        {[property.location, property.city].filter(Boolean).join(', ') || 'Location on request'}
                    </span>
                </div>

                <div className="property-footer">
                    <span className="property-id">
                        ID: {property.property_id || 'N/A'}
                    </span>
                    <button
                        type="button"
                        className="contact-property-btn"
                        onClick={() => onSelectForEnquiry(property)}
                    >
                        <span>Schedule Visit / Inquire</span>
                        <span className="arrow">→</span>
                    </button>
                </div>
            </div>
        </article>
    );
}
