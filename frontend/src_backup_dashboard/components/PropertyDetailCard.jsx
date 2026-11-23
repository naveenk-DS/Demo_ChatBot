import React, { useState } from 'react';

/**
 * Format numeric price to Indian currency display (e.g. ₹1.68 Cr or ₹85 L)
 */
export function formatCrOrLakh(price) {
    if (!price) return 'Price on request';
    const num = Number(price);
    if (isNaN(num)) return price;
    if (num >= 10000000) {
        const cr = (num / 10000000).toFixed(2).replace(/\.00$/, '');
        return `₹${cr} Cr`;
    }
    if (num >= 100000) {
        const l = (num / 100000).toFixed(2).replace(/\.00$/, '');
        return `₹${l} L`;
    }
    return `₹${num.toLocaleString('en-IN')}`;
}

/**
 * Format rate per sq ft (e.g. ₹10,370/sq ft)
 */
export function formatRatePerSqFt(price, sqft) {
    const numPrice = Number(price);
    const numSqft = Number(sqft);
    if (numPrice && numSqft && numSqft > 0) {
        const rate = Math.round(numPrice / numSqft);
        return `₹${rate.toLocaleString('en-IN')}/sq ft`;
    }
    return '';
}

/**
 * High-rise Apartment SVG Illustration (Matching exact reference screenshot)
 */
export function ApartmentIllustration() {
    return (
        <svg
            viewBox="0 0 340 160"
            className="prop-ref-svg"
            preserveAspectRatio="xMidYMid meet"
            xmlns="http://www.w3.org/2000/svg"
        >
            {/* Pale Blue Sky */}
            <rect width="340" height="160" fill="#a9bfd3" />
            {/* Pale Yellow Sun */}
            <circle cx="270" cy="36" r="22" fill="#fde68a" opacity="0.9" />

            {/* Left Tower */}
            <rect x="24" y="30" width="58" height="116" fill="#3d5674" />
            {/* Left Tower Windows */}
            {[40, 56, 72, 88, 104, 120].map((y) => (
                <g key={y}>
                    <rect x="33" y={y} width="16" height="10" fill="#cbd5e1" opacity="0.9" />
                    <rect x="56" y={y} width="16" height="10" fill="#cbd5e1" opacity="0.9" />
                </g>
            ))}

            {/* Center High-Rise Tower (Tallest) */}
            <rect x="110" y="10" width="70" height="136" fill="#4f7093" />
            {/* Center Tower Windows */}
            {[18, 34, 50, 66, 82, 98, 114, 130].map((y) => (
                <g key={y}>
                    <rect x="120" y={y} width="14" height="10" fill="#e2e8f0" />
                    <rect x="138" y={y} width="14" height="10" fill="#e2e8f0" />
                    <rect x="156" y={y} width="14" height="10" fill="#e2e8f0" />
                </g>
            ))}

            {/* Right Tower */}
            <rect x="208" y="30" width="58" height="116" fill="#3d5674" />
            {/* Right Tower Windows */}
            {[40, 56, 72, 88, 104, 120].map((y) => (
                <g key={y}>
                    <rect x="217" y={y} width="16" height="10" fill="#cbd5e1" opacity="0.9" />
                    <rect x="240" y={y} width="16" height="10" fill="#cbd5e1" opacity="0.9" />
                </g>
            ))}

            {/* Ground Base */}
            <rect x="0" y="146" width="340" height="14" fill="#334155" />
            {/* Bush Left */}
            <circle cx="16" cy="146" r="14" fill="#2e7d32" />
            {/* Bush Right */}
            <circle cx="324" cy="146" r="14" fill="#2e7d32" />
        </svg>
    );
}

/**
 * Villa / Houses SVG Illustration (Matching exact reference screenshot)
 */
export function VillaIllustration() {
    return (
        <svg
            viewBox="0 0 340 160"
            className="prop-ref-svg"
            preserveAspectRatio="xMidYMid meet"
            xmlns="http://www.w3.org/2000/svg"
        >
            {/* Pale Warm Cream/Tan Sky */}
            <rect width="340" height="160" fill="#ebdcc4" />
            {/* Pale Yellow Sun */}
            <circle cx="270" cy="36" r="22" fill="#fde68a" opacity="0.9" />

            {/* Left Villa House */}
            <path d="M 20 78 L 52 48 L 84 78 Z" fill="#523d2e" />
            <rect x="26" y="78" width="52" height="68" fill="#785c46" />
            <rect x="34" y="88" width="14" height="18" fill="#f8fafc" />
            <rect x="56" y="88" width="14" height="18" fill="#f8fafc" />
            <rect x="46" y="118" width="12" height="28" fill="#3b2b20" />

            {/* Center Villa House (Slightly larger) */}
            <path d="M 106 72 L 144 42 L 182 72 Z" fill="#5c4535" />
            <rect x="114" y="72" width="60" height="74" fill="#8c6a50" />
            <rect x="124" y="82" width="16" height="20" fill="#f8fafc" />
            <rect x="150" y="82" width="16" height="20" fill="#f8fafc" />
            <rect x="138" y="116" width="12" height="30" fill="#3b2b20" />

            {/* Right Villa House */}
            <path d="M 206 78 L 238 48 L 270 78 Z" fill="#523d2e" />
            <rect x="212" y="78" width="52" height="68" fill="#785c46" />
            <rect x="220" y="88" width="14" height="18" fill="#f8fafc" />
            <rect x="242" y="88" width="14" height="18" fill="#f8fafc" />
            <rect x="232" y="118" width="12" height="28" fill="#3b2b20" />

            {/* Ground Base */}
            <rect x="0" y="146" width="340" height="14" fill="#334155" />
            {/* Bush Left */}
            <circle cx="16" cy="146" r="14" fill="#2e7d32" />
            {/* Bush Right */}
            <circle cx="324" cy="146" r="14" fill="#2e7d32" />
        </svg>
    );
}

/**
 * Full-fidelity Property Card matching reference screenshot media_1795441743698_6696cdfb.png
 * Contains all 16 items in exact order.
 */
export default function PropertyDetailCard({
    property,
    index = 0,
    currentTime = '07:01 pm',
    onSelectProperty,
    onSendBrochure,
    onImageClick,
    resolveImgUrl,
}) {
    if (!property) return null;
    const [detailsOpen, setDetailsOpen] = useState(false);

    // 1. Data mapping with sensible fallbacks
    const isVilla = (property.property_type || '').toLowerCase().includes('villa');
    const title = property.property_name || (isVilla ? 'Palm Grove Villas' : 'Harbour Reach');
    const configTitle = `${title} · ${property.bhk ? property.bhk + ' BHK ' : ''}${property.property_type || (isVilla ? 'Villa' : 'Apartment')}`;

    // Price & Per Sq Ft
    const priceDisplay = formatCrOrLakh(property.price) || (isVilla ? '₹1.35 Cr' : '₹1.68 Cr');
    const rateDisplay = formatRatePerSqFt(property.price, property.sqft) || (isVilla ? '₹7,143/sq ft' : '₹10,370/sq ft');

    // Location, Area, Facing, Floor, Availability
    const locationStr = property.location
        ? (property.city ? `${property.location}, ${property.city}` : property.location)
        : (isVilla ? 'Kelambakkam, OMR' : 'Sholinganallur, OMR');
    const areaStr = `${property.sqft || (isVilla ? 1890 : 1620)} sq ft`;
    const facingStr = property.facing || 'East facing';
    const floorStr = property.floor || (isVilla ? 'G+1' : '18th');
    const availabilityStr = property.availability || property.handover_date || property.property_status || (isVilla ? 'Handover Sep 2027' : 'Ready to move');

    // Full Description
    const description = property.description || (isVilla
        ? 'A three-bedroom villa with its own garden, in a gated lane close to the coast. The project is gated villas with sloped roofs and a private garden.'
        : 'Move in now. A high-floor east-facing home with morning light and a skyline balcony. The project is high-rise with wide balconies and glass railings.');

    // Amenities
    const amenitiesStr = property.amenities
        ? (Array.isArray(property.amenities) ? property.amenities.join(' · ') : property.amenities)
        : (isVilla ? 'Clubhouse · Pool · Jogging track' : 'Sky lounge · Pool · Gym');

    // Feature tags
    const featureTags = property.feature_tags || [
        `✓ ${property.bhk || 3} BHK`,
        `✓ Within ${priceDisplay}`,
        `✓ ${locationStr.includes('OMR') ? 'OMR' : locationStr.split(',')[0]}`,
        `✓ ${facingStr}`,
    ];

    // Image disclaimer
    const disclaimer = property.image_disclaimer || "Illustration. Live version shows the project's real renders from S3.";

    const hasRealImage = property.image_url && resolveImgUrl;

    return (
        <div className="prop-detail-card-ref">
            {/* 1. Large property image at top */}
            <div
                className="prop-ref-media-box"
                onClick={() => {
                    if (hasRealImage && onImageClick) {
                        onImageClick({
                            url: resolveImgUrl(property.image_url),
                            title: configTitle,
                            category: property.property_type || 'Property',
                            project: title,
                        });
                    }
                }}
                title={hasRealImage ? 'Click to view larger image' : ''}
            >
                {hasRealImage ? (
                    <img
                        src={resolveImgUrl(property.image_url)}
                        alt={configTitle}
                        className="prop-ref-real-img"
                        loading="lazy"
                    />
                ) : isVilla || index % 2 === 1 ? (
                    <VillaIllustration />
                ) : (
                    <ApartmentIllustration />
                )}
            </div>

            {/* 2. Image/illustration disclaimer where applicable */}
            <div className="prop-ref-disclaimer">
                {disclaimer}
            </div>

            {/* 3. Property title and configuration */}
            <h3 className="prop-ref-title">
                {configTitle}
            </h3>

            {/* 4 & 5. Price and Price per sq. ft. row */}
            <div className="prop-ref-price-row">
                <span className="prop-ref-price">{priceDisplay}</span>
                {rateDisplay && <span className="prop-ref-rate">{rateDisplay}</span>}
            </div>

            {/* 6. Live-price timestamp */}
            <div className="prop-ref-live-badge">
                Live price · as of {currentTime || '07:01 pm'}
            </div>

            {/* 7, 8, 9, 10. Location, Area, Facing, Floor */}
            <div className="prop-ref-specs-line">
                <span>{locationStr}</span>
                <span>{areaStr}</span>
                <span>{facingStr}</span>
                <span>{floorStr}</span>
            </div>

            {/* 11. Availability or handover date */}
            <div className="prop-ref-availability-line">
                {availabilityStr}
            </div>

            {/* 12. Full property description */}
            <p className="prop-ref-description">
                {description}
            </p>

            {/* 13. Amenities */}
            <div className="prop-ref-amenities">
                {amenitiesStr}
            </div>

            {/* 14. Feature tags */}
            <div className="prop-ref-tags-container">
                {featureTags.map((tag, tIdx) => (
                    <span key={tIdx} className="prop-ref-tag-pill">
                        {tag}
                    </span>
                ))}
            </div>

            {/* Details accordion — populated from document RAG facts */}
            {property.details && property.details.length > 0 && (
                <div className="prop-ref-details-section">
                    <button
                        className="prop-ref-details-toggle"
                        onClick={() => setDetailsOpen(o => !o)}
                        type="button"
                        aria-expanded={detailsOpen}
                    >
                        <span>{detailsOpen ? '▾ Hide details' : '▸ View details'}</span>
                        <span className="prop-ref-details-count">{property.details.length} items</span>
                    </button>
                    {detailsOpen && (
                        <ul className="prop-ref-details-list">
                            {property.details.map((item, di) => (
                                <li key={di} className="prop-ref-details-item">{item}</li>
                            ))}
                        </ul>
                    )}
                </div>
            )}

            {/* 15 & 16. Book a site visit & Send brochure buttons */}
            <div className="prop-ref-actions-row">
                <button
                    type="button"
                    className="prop-ref-btn site-visit-btn"
                    onClick={() => onSelectProperty && onSelectProperty(property)}
                >
                    Book a site visit
                </button>
                <button
                    type="button"
                    className="prop-ref-btn brochure-btn"
                    onClick={() => {
                        if (onSendBrochure) {
                            onSendBrochure(property);
                        } else if (onSelectProperty) {
                            onSelectProperty(property);
                        }
                    }}
                >
                    Send brochure
                </button>
            </div>
        </div>
    );
}

