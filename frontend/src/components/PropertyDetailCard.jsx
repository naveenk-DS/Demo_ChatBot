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
 * High-rise Apartment SVG Illustration
 */
export function ApartmentIllustration() {
    return (
        <svg viewBox="0 0 340 160" className="prop-ref-svg" preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg">
            <rect width="340" height="160" fill="#1e293b" />
            <circle cx="270" cy="36" r="22" fill="#60a5fa" opacity="0.4" />
            <rect x="24" y="30" width="58" height="116" fill="#334155" />
            {[40, 56, 72, 88, 104, 120].map((y) => (
                <g key={y}>
                    <rect x="33" y={y} width="16" height="10" fill="#94a3b8" opacity="0.85" />
                    <rect x="56" y={y} width="16" height="10" fill="#94a3b8" opacity="0.85" />
                </g>
            ))}
            <rect x="110" y="10" width="70" height="136" fill="#2563eb" opacity="0.85" />
            {[18, 34, 50, 66, 82, 98, 114, 130].map((y) => (
                <g key={y}>
                    <rect x="120" y={y} width="14" height="10" fill="#e2e8f0" />
                    <rect x="138" y={y} width="14" height="10" fill="#e2e8f0" />
                    <rect x="156" y={y} width="14" height="10" fill="#e2e8f0" />
                </g>
            ))}
            <rect x="208" y="30" width="58" height="116" fill="#334155" />
            {[40, 56, 72, 88, 104, 120].map((y) => (
                <g key={y}>
                    <rect x="217" y={y} width="16" height="10" fill="#94a3b8" opacity="0.85" />
                    <rect x="240" y={y} width="16" height="10" fill="#94a3b8" opacity="0.85" />
                </g>
            ))}
            <rect x="0" y="146" width="340" height="14" fill="#0f172a" />
            <circle cx="16" cy="146" r="14" fill="#059669" />
            <circle cx="324" cy="146" r="14" fill="#059669" />
        </svg>
    );
}

/**
 * Villa / Houses SVG Illustration
 */
export function VillaIllustration() {
    return (
        <svg viewBox="0 0 340 160" className="prop-ref-svg" preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg">
            <rect width="340" height="160" fill="#0f172a" />
            <circle cx="270" cy="36" r="22" fill="#38bdf8" opacity="0.3" />
            <path d="M 20 78 L 52 48 L 84 78 Z" fill="#1e293b" />
            <rect x="26" y="78" width="52" height="68" fill="#334155" />
            <rect x="34" y="88" width="14" height="18" fill="#cbd5e1" />
            <rect x="56" y="88" width="14" height="18" fill="#cbd5e1" />
            <rect x="46" y="118" width="12" height="28" fill="#2563eb" />
            <path d="M 106 72 L 144 42 L 182 72 Z" fill="#1e3a8a" />
            <rect x="114" y="72" width="60" height="74" fill="#2563eb" opacity="0.8" />
            <rect x="124" y="82" width="16" height="20" fill="#f8fafc" />
            <rect x="150" y="82" width="16" height="20" fill="#f8fafc" />
            <rect x="138" y="116" width="12" height="30" fill="#0f172a" />
            <path d="M 206 78 L 238 48 L 270 78 Z" fill="#1e293b" />
            <rect x="212" y="78" width="52" height="68" fill="#334155" />
            <rect x="220" y="88" width="14" height="18" fill="#cbd5e1" />
            <rect x="242" y="88" width="14" height="18" fill="#cbd5e1" />
            <rect x="232" y="118" width="12" height="28" fill="#2563eb" />
            <rect x="0" y="146" width="340" height="14" fill="#020617" />
            <circle cx="16" cy="146" r="14" fill="#059669" />
            <circle cx="324" cy="146" r="14" fill="#059669" />
        </svg>
    );
}

/**
 * Living Room Architectural SVG
 */
export function LivingRoomSvg() {
    return (
        <svg viewBox="0 0 200 130" className="prop-room-svg" xmlns="http://www.w3.org/2000/svg">
            <rect width="200" height="130" fill="#0f172a" />
            {/* Window with sunlight */}
            <rect x="120" y="15" width="65" height="70" fill="#1e293b" stroke="#38bdf8" strokeWidth="1.5" />
            <line x1="152" y1="15" x2="152" y2="85" stroke="#38bdf8" strokeWidth="1" />
            <line x1="120" y1="50" x2="185" y2="50" stroke="#38bdf8" strokeWidth="1" />
            {/* Sofa */}
            <rect x="20" y="60" width="85" height="38" rx="6" fill="#2563eb" opacity="0.9" />
            <rect x="25" y="52" width="75" height="18" rx="4" fill="#1d4ed8" />
            <rect x="16" y="66" width="10" height="28" rx="3" fill="#1e40af" />
            <rect x="99" y="66" width="10" height="28" rx="3" fill="#1e40af" />
            {/* Coffee Table */}
            <rect x="42" y="102" width="46" height="14" rx="3" fill="#475569" />
            {/* Floor tile grid */}
            <line x1="0" y1="118" x2="200" y2="118" stroke="#334155" strokeWidth="1" />
            <circle cx="170" cy="100" r="12" fill="#059669" opacity="0.8" />
        </svg>
    );
}

/**
 * Kitchen Architectural SVG
 */
export function KitchenSvg() {
    return (
        <svg viewBox="0 0 200 130" className="prop-room-svg" xmlns="http://www.w3.org/2000/svg">
            <rect width="200" height="130" fill="#0f172a" />
            {/* Upper Cabinets */}
            <rect x="15" y="12" width="170" height="30" fill="#1e293b" stroke="#334155" strokeWidth="1" />
            <line x1="72" y1="12" x2="72" y2="42" stroke="#334155" strokeWidth="1" />
            <line x1="128" y1="12" x2="128" y2="42" stroke="#334155" strokeWidth="1" />
            {/* Countertop */}
            <rect x="15" y="70" width="170" height="12" fill="#0284c7" />
            {/* Lower Cabinets */}
            <rect x="15" y="82" width="170" height="40" fill="#1e293b" stroke="#334155" strokeWidth="1" />
            <line x1="60" y1="82" x2="60" y2="122" stroke="#334155" strokeWidth="1" />
            <line x1="110" y1="82" x2="110" y2="122" stroke="#334155" strokeWidth="1" />
            <line x1="155" y1="82" x2="155" y2="122" stroke="#334155" strokeWidth="1" />
            {/* Chimney / Hob */}
            <rect x="80" y="42" width="40" height="14" fill="#475569" />
            <circle cx="92" cy="66" r="4" fill="#ef4444" opacity="0.8" />
            <circle cx="108" cy="66" r="4" fill="#ef4444" opacity="0.8" />
        </svg>
    );
}

/**
 * Balcony Architectural SVG
 */
export function BalconySvg() {
    return (
        <svg viewBox="0 0 200 130" className="prop-room-svg" xmlns="http://www.w3.org/2000/svg">
            <rect width="200" height="130" fill="#0a192f" />
            {/* Sky gradient background */}
            <rect x="0" y="0" width="200" height="75" fill="#172554" />
            <circle cx="160" cy="28" r="14" fill="#38bdf8" opacity="0.5" />
            {/* Distant skyline */}
            <rect x="20" y="38" width="20" height="37" fill="#1e3a8a" opacity="0.5" />
            <rect x="45" y="24" width="25" height="51" fill="#1e3a8a" opacity="0.6" />
            <rect x="75" y="34" width="20" height="41" fill="#1e3a8a" opacity="0.5" />
            {/* Balcony Railing */}
            <rect x="10" y="75" width="180" height="50" fill="#0f172a" />
            <line x1="10" y1="75" x2="190" y2="75" stroke="#38bdf8" strokeWidth="2.5" />
            <line x1="10" y1="95" x2="190" y2="95" stroke="#475569" strokeWidth="1.5" />
            {[25, 45, 65, 85, 105, 125, 145, 165, 185].map((x) => (
                <line key={x} x1={x} y1="75" x2={x} y2="125" stroke="#475569" strokeWidth="1" />
            ))}
            {/* Plant Pot */}
            <circle cx="35" cy="115" r="8" fill="#10b981" />
        </svg>
    );
}

/**
 * Technical Floor Plan Blueprint SVG
 */
export function FloorPlanSvg({ bhk = 3 }) {
    return (
        <svg viewBox="0 0 320 200" className="prop-floorplan-svg" xmlns="http://www.w3.org/2000/svg">
            <rect width="320" height="200" fill="#09131d" />
            {/* Grid lines */}
            {[20, 40, 60, 80, 100, 120, 140, 160, 180].map((y) => (
                <line key={y} x1="0" y1={y} x2="320" y2={y} stroke="#1e293b" strokeWidth="0.5" strokeDasharray="3 3" />
            ))}
            {[40, 80, 120, 160, 200, 240, 280].map((x) => (
                <line key={x} x1={x} y1="0" x2={x} y2="200" stroke="#1e293b" strokeWidth="0.5" strokeDasharray="3 3" />
            ))}
            {/* Outer Wall Boundary */}
            <rect x="25" y="20" width="270" height="160" fill="none" stroke="#2563eb" strokeWidth="3" />
            
            {/* Living & Dining Area */}
            <rect x="25" y="20" width="150" height="90" fill="#172554" opacity="0.35" stroke="#38bdf8" strokeWidth="1.5" />
            <text x="50" y="55" fill="#ffffff" fontSize="11" fontWeight="700">LIVING & DINING</text>
            <text x="50" y="70" fill="#38bdf8" fontSize="9.5">{bhk === 2 ? "12' x 24' 3\"" : (bhk === 4 ? "16' x 28'" : "25' 1\" x 15'")}</text>

            {/* Balcony */}
            <rect x="25" y="110" width="80" height="40" fill="#1e293b" opacity="0.4" stroke="#38bdf8" strokeWidth="1.5" />
            <text x="35" y="130" fill="#ffffff" fontSize="9" fontWeight="700">BALCONY</text>
            <text x="35" y="142" fill="#94a3b8" fontSize="8.5">{bhk === 2 ? "4' 6\" WIDE" : "6' 0\" WIDE"}</text>

            {/* Kitchen */}
            <rect x="105" y="110" width="70" height="70" fill="#172554" opacity="0.2" stroke="#38bdf8" strokeWidth="1.5" />
            <text x="115" y="138" fill="#ffffff" fontSize="9" fontWeight="700">KITCHEN</text>
            <text x="115" y="152" fill="#38bdf8" fontSize="8.5">{bhk === 2 ? "8' 2\" x 14'" : "16' x 9'"}</text>

            {/* Master Bedroom */}
            <rect x="175" y="20" width="120" height="85" fill="#1e3a8a" opacity="0.35" stroke="#38bdf8" strokeWidth="1.5" />
            <text x="185" y="52" fill="#ffffff" fontSize="10" fontWeight="700">MASTER BEDROOM</text>
            <text x="185" y="67" fill="#38bdf8" fontSize="9">{bhk === 2 ? "11' 6\" x 14'" : (bhk === 4 ? "14' x 18'" : "11' x 18' 2\"")}</text>

            {/* Bedroom 2 */}
            <rect x="175" y="105" width="120" height="75" fill="#1e293b" opacity="0.3" stroke="#38bdf8" strokeWidth="1.5" />
            <text x="185" y="136" fill="#ffffff" fontSize="9.5" fontWeight="700">BEDROOM 2</text>
            <text x="185" y="150" fill="#38bdf8" fontSize="8.5">{bhk === 2 ? "11' 1\" x 14' 2\"" : "13' x 14'"}</text>

            {/* Compass Indicator */}
            <g transform="translate(280, 42)">
                <circle cx="0" cy="0" r="10" fill="#0f172a" stroke="#38bdf8" strokeWidth="1" />
                <path d="M 0 -8 L 3 0 L -3 0 Z" fill="#ef4444" />
                <path d="M 0 8 L 3 0 L -3 0 Z" fill="#94a3b8" />
                <text x="-3" y="-11" fill="#ef4444" fontSize="7" fontWeight="bold">N</text>
            </g>
        </svg>
    );
}

/**
 * 360 Virtual Tour Simulation SVG
 */
export function VirtualTourSvg() {
    return (
        <svg viewBox="0 0 320 180" className="prop-floorplan-svg" xmlns="http://www.w3.org/2000/svg">
            <rect width="320" height="180" fill="#09131d" />
            {/* Horizon curvature */}
            <path d="M 0 90 Q 160 50 320 90 L 320 180 L 0 180 Z" fill="#0f1f33" />
            <path d="M 0 90 Q 160 130 320 90 L 320 0 L 0 0 Z" fill="#060c14" />
            {/* Panorama grid lines */}
            <ellipse cx="160" cy="90" rx="140" ry="50" fill="none" stroke="#2563eb" strokeWidth="1.5" strokeDasharray="6 4" opacity="0.7" />
            <circle cx="160" cy="90" r="32" fill="#2563eb" opacity="0.25" />
            <circle cx="160" cy="90" r="22" fill="#2563eb" opacity="0.6" />
            {/* 360 arrow icon */}
            <path d="M 150 90 A 10 10 0 1 1 170 90" fill="none" stroke="#ffffff" strokeWidth="2.5" />
            <polygon points="172,86 172,94 178,90" fill="#ffffff" />
            <text x="160" y="145" textAnchor="middle" fill="#ffffff" fontSize="13" fontWeight="700">360° Interactive Tour Available</text>
            <text x="160" y="162" textAnchor="middle" fill="#94a3b8" fontSize="10.5">Click Launch 360° Walkthrough to explore high-res panoramic view</text>
        </svg>
    );
}

/**
 * Build dynamic 6 room tiles based on BHK configuration & actual documents
 */
export function getRoomTilesForBHK(bhkNum, propertyDetails = []) {
    const bhk = Number(bhkNum) || 3;

    // Helper to find document fact if present
    const findFact = (keyword, fallback) => {
        if (!propertyDetails || propertyDetails.length === 0) return fallback;
        const matched = propertyDetails.find(d => typeof d === 'string' && d.toLowerCase().includes(keyword.toLowerCase()));
        return matched ? matched : fallback;
    };

    if (bhk === 2) {
        return [
            {
                id: 'living',
                name: 'Living & Dining',
                tag: 'LIVING & DINING',
                dimension: "12' x 24' 3\"",
                spec: findFact('living', '4\' x 2\' Vitrified Tiles • Opens to Balcony'),
                imageKey: 'living',
            },
            {
                id: 'bed1',
                name: 'Bedroom 1 (Master)',
                tag: 'BEDROOM 1',
                dimension: "11' 6\" x 14' 0\"",
                spec: findFact('master bedroom', 'King Size Bed • Convertible Balcony'),
                imageKey: 'bedroom1',
                imageUrl: '/api/assets/images/Bedroom.jpg',
            },
            {
                id: 'bed2',
                name: 'Bedroom 2',
                tag: 'BEDROOM 2',
                dimension: "11' 1\" x 14' 2\"",
                spec: findFact('bedroom 2', 'Southwest Vaastu • Large Windows'),
                imageKey: 'bedroom2',
                imageUrl: '/api/assets/images/bedroom.jpg.2.jpg',
            },
            {
                id: 'kitchen',
                name: 'Kitchen',
                tag: 'KITCHEN',
                dimension: "8' 2\" x 14' 0\"",
                spec: findFact('kitchen', 'Northeast Vaastu • Separate Utility Area'),
                imageKey: 'kitchen',
            },
            {
                id: 'balcony',
                name: 'Balcony',
                tag: 'BALCONY',
                dimension: "4' 6\" Wide",
                spec: findFact('balcony', '2\' x 2\' Anti-skid Ceramic Tiles'),
                imageKey: 'balcony',
            },
            {
                id: 'bathrooms',
                name: 'Bathrooms (2T)',
                tag: 'BATHROOMS',
                dimension: "8' 6\" x 5' & 5' x 8'",
                spec: findFact('bath', 'Wall Hung Wash Basin • Anti-skid Flooring'),
                imageKey: 'bathroom',
                imageUrl: '/api/assets/images/Bathroom.jpg',
            },
        ];
    } else if (bhk >= 4) {
        return [
            {
                id: 'living',
                name: 'Living & Dining',
                tag: 'LIVING & DINING',
                dimension: "16' 0\" x 28' 0\"",
                spec: findFact('living', 'Large Vitrified Tiles 4\' x 2\' • Skyline Deck'),
                imageKey: 'living',
            },
            {
                id: 'bed1',
                name: 'Master Suite',
                tag: 'BEDROOM 1',
                dimension: "14' 0\" x 18' 0\"",
                spec: findFact('master', 'Private Master Balcony & Walk-in Wardrobe'),
                imageKey: 'bedroom1',
                imageUrl: '/api/assets/images/Bedroom.jpg',
            },
            {
                id: 'bed2',
                name: 'Bedroom 2 & 3',
                tag: 'BEDROOM 2',
                dimension: "13' 0\" x 15' 0\"",
                spec: findFact('bedroom', 'En-suite Bathrooms • Panoramic Windows'),
                imageKey: 'bedroom2',
                imageUrl: '/api/assets/images/bedroom.jpg.2.jpg',
            },
            {
                id: 'kitchen',
                name: 'Kitchen & Utility',
                tag: 'KITCHEN',
                dimension: "10' 0\" x 14' 0\"",
                spec: findFact('kitchen', 'Separate Utility Space • Premium CP Fittings'),
                imageKey: 'kitchen',
            },
            {
                id: 'balcony',
                name: 'Sky Deck Balcony',
                tag: 'BALCONY',
                dimension: "7' 0\" Wide Deck",
                spec: findFact('balcony', 'Glass Railings • Anti-skid Ceramic Flooring'),
                imageKey: 'balcony',
            },
            {
                id: 'bathrooms',
                name: 'Luxury Bathrooms (4T)',
                tag: 'BATHROOMS',
                dimension: "4 Full Bathrooms",
                spec: findFact('bath', 'Reputed Brand CP & Sanitary Fittings'),
                imageKey: 'bathroom',
                imageUrl: '/api/assets/images/Bathroom.jpg',
            },
        ];
    } else {
        // Default 3BHK
        return [
            {
                id: 'living',
                name: 'Living & Dining',
                tag: 'LIVING & DINING',
                dimension: "25' 1\" x 15' 0\"",
                spec: findFact('living', '4\' x 2\' Vitrified Tiles • Opens to 6\' Balcony'),
                imageKey: 'living',
            },
            {
                id: 'bed1',
                name: 'Master Bedroom',
                tag: 'BEDROOM 1',
                dimension: "11' 0\" x 18' 2\"",
                spec: findFact('master', 'Accommodates King Bed & Seaters • Balcony'),
                imageKey: 'bedroom1',
                imageUrl: '/api/assets/images/Bedroom.jpg',
            },
            {
                id: 'bed2',
                name: 'Bedroom 2',
                tag: 'BEDROOM 2',
                dimension: "13' 0\" x 14' 0\"",
                spec: findFact('bedroom 2', 'King Bed • Convertible Balcony • Wardrobe'),
                imageKey: 'bedroom2',
                imageUrl: '/api/assets/images/bedroom.jpg.2.jpg',
            },
            {
                id: 'kitchen',
                name: 'Kitchen',
                tag: 'KITCHEN',
                dimension: "16' 0\" x 9' 0\"",
                spec: findFact('kitchen', 'Southeast Vaastu • Wide Windows & Utility'),
                imageKey: 'kitchen',
            },
            {
                id: 'balcony',
                name: 'Balcony',
                tag: 'BALCONY',
                dimension: "6' 0\" Wide",
                spec: findFact('balcony', '2\' x 2\' Anti-skid Ceramic Tiles • Views'),
                imageKey: 'balcony',
            },
            {
                id: 'bathrooms',
                name: 'Bathrooms (3T)',
                tag: 'BATHROOMS',
                dimension: "6' x 9' & 9' x 6'",
                spec: findFact('bath', '3 Bathrooms with Anti-skid Ceramic Tiles'),
                imageKey: 'bathroom',
                imageUrl: '/api/assets/images/Bathroom.jpg',
            },
        ];
    }
}

/**
 * Complete Two-Screen Property Detail Card
 * SCREEN 1 — PROPERTY OVERVIEW
 * SCREEN 2 — PROPERTY SPECIFICATIONS (2-Column Visual Tiles Grid)
 */
export default function PropertyDetailCard({
    property,
    index = 0,
    onSelectProperty,
    onSendBrochure,
    onImageClick,
    resolveImgUrl,
}) {
    if (!property) return null;

    // Active Navigation Tab: 'overview' | 'specifications' | 'floorplan' | 'images' | 'virtualtour' | 'amenities'
    const [activeTab, setActiveTab] = useState('overview');

    // Hero Image Index (for image navigation < and > on large hero image)
    const [heroImageIdx, setHeroImageIdx] = useState(0);

    // Data extraction
    const isVilla = (property.property_type || '').toLowerCase().includes('villa');
    const title = property.property_name || (isVilla ? 'Palm Grove Villas' : 'Harbour Reach');
    const bhkNum = Number(property.bhk) || (isVilla ? 3 : 3);
    const configTitle = `${title} · ${bhkNum} BHK ${property.property_type || (isVilla ? 'Villa' : 'Apartment')}`;

    // Price & Per Sq Ft
    const priceDisplay = property.price ? formatCrOrLakh(property.price) : (property.price_display || 'Price on request');
    const rateDisplay = (property.price && property.sqft) ? formatRatePerSqFt(property.price, property.sqft) : '₹10,370/sq ft';

    // Location, Area, Facing, Floor, Availability
    const locationStr = property.location
        ? (property.city && !property.location.toLowerCase().includes(property.city.toLowerCase())
            ? `${property.location}, ${property.city}`
            : property.location)
        : (property.city || 'Sholinganallur, OMR');
    const areaStr = property.sqft ? `${property.sqft} sq ft` : (property.area ? `${property.area} sq ft` : (bhkNum === 2 ? '1250 sq ft' : (bhkNum === 4 ? '2300 sq ft' : '1620 sq ft')));
    const facingStr = property.facing || 'East facing';
    const floorStr = property.floor ? (property.floor.toLowerCase().includes('floor') ? property.floor : `${property.floor} floor`) : '18th floor';
    const availabilityStr = property.availability || property.handover_date || property.property_status || 'Ready to move';

    // Full Description
    const description = property.description || (isVilla
        ? 'A three-bedroom villa with its own garden, in a gated lane close to the coast. The project is gated villas with sloped roofs and a private garden.'
        : 'Move in now. A high-floor east-facing home with morning light and a skyline balcony. The project is high-rise with wide balconies and glass railings.');

    // Amenities
    const amenitiesList = Array.isArray(property.amenities)
        ? property.amenities
        : (property.amenities ? property.amenities.split('·').map(s => s.trim()) : ['Clubhouse', 'Swimming Pool', 'Sky Lounge', 'Gym', 'Jogging Track', 'Badminton Court']);

    // Feature tags
    const featureTags = property.feature_tags || [
        `✓ ${bhkNum} BHK`,
        `✓ ${priceDisplay}`,
        `✓ ${locationStr.split(',')[0].trim()}`,
        `✓ ${facingStr}`,
    ];

    // Room tiles for Screen 2
    const roomTiles = getRoomTilesForBHK(bhkNum, property.details || []);

    // Catalog of available photos/images for hero slider
    const heroImages = [
        ...(property.image_url ? [{ url: property.image_url, label: 'Exterior Render' }] : []),
        { url: '/api/assets/images/Bedroom.jpg', label: 'Master Bedroom' },
        { url: '/api/assets/images/Bathroom.jpg', label: 'Luxury Bathroom' },
        { url: '/api/assets/images/bedroom.jpg.2.jpg', label: 'Bedroom 2' },
    ];

    const currentHero = heroImages[heroImageIdx % heroImages.length];

    const handlePrevHero = (e) => {
        if (e) e.stopPropagation();
        setHeroImageIdx(prev => (prev > 0 ? prev - 1 : heroImages.length - 1));
    };

    const handleNextHero = (e) => {
        if (e) e.stopPropagation();
        setHeroImageIdx(prev => (prev < heroImages.length - 1 ? prev + 1 : 0));
    };

    const handleTileClick = (tile) => {
        if (onImageClick) {
            onImageClick({
                url: tile.imageUrl ? (resolveImgUrl ? resolveImgUrl(tile.imageUrl) : tile.imageUrl) : null,
                title: `${tile.name} — ${configTitle}`,
                category: tile.tag,
                project: title,
                specs: `${tile.dimension} • ${tile.spec}`,
            });
        }
    };

    return (
        <div className="prop-detail-card-ref animate-fade-in">
            {/* Top Navigation Bar: Screen 1 vs Screen 2 */}
            <div className="prop-screen-tabs-bar">
                <button
                    type="button"
                    className={`prop-screen-tab-btn ${activeTab === 'overview' ? 'active' : ''}`}
                    onClick={() => setActiveTab('overview')}
                >
                    Overview
                </button>
                <button
                    type="button"
                    className={`prop-screen-tab-btn ${activeTab === 'specifications' ? 'active' : ''}`}
                    onClick={() => setActiveTab('specifications')}
                >
                    Specifications
                </button>
                <button
                    type="button"
                    className={`prop-screen-tab-btn ${activeTab === 'floorplan' ? 'active' : ''}`}
                    onClick={() => setActiveTab('floorplan')}
                >
                    Floor Plan
                </button>
                <button
                    type="button"
                    className={`prop-screen-tab-btn ${activeTab === 'images' ? 'active' : ''}`}
                    onClick={() => setActiveTab('images')}
                >
                    Images
                </button>
                <button
                    type="button"
                    className={`prop-screen-tab-btn ${activeTab === 'virtualtour' ? 'active' : ''}`}
                    onClick={() => setActiveTab('virtualtour')}
                >
                    Virtual Tour
                </button>
            </div>

            {/* ============================================================== */}
            {/* SCREEN 1: PROPERTY OVERVIEW                                    */}
            {/* ============================================================== */}
            {activeTab === 'overview' && (
                <div className="prop-overview-screen animate-fade-in">
                    {/* 1. Large Hero Media Box with Navigation Arrows */}
                    <div className="prop-ref-media-box">
                        {currentHero && currentHero.url && resolveImgUrl ? (
                            <img
                                src={resolveImgUrl(currentHero.url)}
                                alt={configTitle}
                                className="prop-ref-real-img"
                                loading="lazy"
                                onClick={() => {
                                    if (onImageClick) {
                                        onImageClick({
                                            url: resolveImgUrl(currentHero.url),
                                            title: `${currentHero.label} — ${configTitle}`,
                                            category: currentHero.label,
                                            project: title,
                                        });
                                    }
                                }}
                            />
                        ) : isVilla || index % 2 === 1 ? (
                            <VillaIllustration />
                        ) : (
                            <ApartmentIllustration />
                        )}

                        {/* Image Navigation Controls */}
                        <div className="prop-media-nav-overlay">
                            <button
                                type="button"
                                className="prop-media-arrow-btn prev"
                                onClick={handlePrevHero}
                                aria-label="Previous photo"
                                title="Previous photo"
                            >
                                ‹
                            </button>
                            <span className="prop-media-counter">
                                {heroImageIdx + 1} / {heroImages.length}
                            </span>
                            <button
                                type="button"
                                className="prop-media-arrow-btn next"
                                onClick={handleNextHero}
                                aria-label="Next photo"
                                title="Next photo"
                            >
                                ›
                            </button>
                        </div>
                    </div>

                    {/* Image disclaimer caption */}
                    <div className="prop-ref-disclaimer">
                        {property.image_disclaimer || "Verified Project Renders & Real Model House Images."}
                    </div>

                    {/* Property Title & BHK Configuration */}
                    <h3 className="prop-ref-title">
                        {configTitle}
                    </h3>

                    {/* Actual Price & Rate per Sq Ft */}
                    <div className="prop-ref-price-row">
                        <span className="prop-ref-price">{priceDisplay}</span>
                        {rateDisplay && <span className="prop-ref-rate">{rateDisplay}</span>}
                    </div>

                    {/* Location, Area, Facing, Floor line */}
                    <div className="prop-ref-specs-line">
                        {locationStr && <span>{locationStr}</span>}
                        {areaStr && <span>{areaStr}</span>}
                        {facingStr && <span>{facingStr}</span>}
                        {floorStr && <span>{floorStr}</span>}
                    </div>

                    {/* Availability / Handover status */}
                    <div className="prop-ref-availability-line">
                        Status: <strong style={{ color: '#10B981' }}>{availabilityStr}</strong>
                    </div>

                    {/* Full Description */}
                    <p className="prop-ref-description">
                        {description}
                    </p>

                    {/* Amenities chips */}
                    <div className="prop-ref-amenities">
                        {amenitiesList.slice(0, 4).join(' · ')}
                    </div>

                    {/* Feature tags */}
                    <div className="prop-ref-tags-container">
                        {featureTags.map((tag, tIdx) => (
                            <span key={tIdx} className="prop-ref-tag-pill">
                                {tag}
                            </span>
                        ))}
                    </div>

                    {/* PROMINENT "VIEW SPECIFICATIONS" BUTTON (Transitions to Screen 2) */}
                    <div className="prop-primary-action-wrap">
                        <button
                            type="button"
                            className="prop-view-specs-primary-btn"
                            onClick={() => setActiveTab('specifications')}
                        >
                            View Specifications ➔
                        </button>
                    </div>

                    {/* Secondary Actions Row: Book site visit & Send brochure */}
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
            )}

            {/* ============================================================== */}
            {/* SCREEN 2: PROPERTY SPECIFICATIONS (2-Column Visual Tiles Grid) */}
            {/* ============================================================== */}
            {activeTab === 'specifications' && (
                <div className="prop-specs-screen animate-fade-in">
                    {/* Header with Back button */}
                    <div className="prop-specs-header-row">
                        <button
                            type="button"
                            className="prop-back-to-overview-btn"
                            onClick={() => setActiveTab('overview')}
                        >
                            ‹ Back to Overview
                        </button>
                        <span className="prop-specs-title-tag">
                            {bhkNum} BHK Specifications
                        </span>
                    </div>

                    {/* Two-Column Visual Image Tiles Grid */}
                    <div className="prop-specs-tiles-grid">
                        {roomTiles.map((tile) => {
                            const hasTileImg = tile.imageUrl && resolveImgUrl;

                            return (
                                <div
                                    key={tile.id}
                                    className="prop-room-tile-card"
                                    onClick={() => handleTileClick(tile)}
                                    title="Click to view full image & specifications"
                                >
                                    {/* Tile Visual Media */}
                                    <div className="prop-room-tile-media">
                                        {hasTileImg ? (
                                            <img
                                                src={resolveImgUrl(tile.imageUrl)}
                                                alt={tile.name}
                                                className="prop-room-tile-img"
                                                loading="lazy"
                                            />
                                        ) : tile.id === 'living' ? (
                                            <LivingRoomSvg />
                                        ) : tile.id === 'kitchen' ? (
                                            <KitchenSvg />
                                        ) : tile.id === 'balcony' ? (
                                            <BalconySvg />
                                        ) : (
                                            <ApartmentIllustration />
                                        )}
                                        <span className="prop-room-tile-tag">
                                            {tile.tag}
                                        </span>
                                    </div>

                                    {/* Tile Content */}
                                    <div className="prop-room-tile-content">
                                        <div className="prop-room-tile-name">
                                            {tile.name}
                                        </div>
                                        <div className="prop-room-tile-dimension">
                                            {tile.dimension}
                                        </div>
                                        <div className="prop-room-tile-spec">
                                            {tile.spec}
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>

                    {/* Bottom Actions Row */}
                    <div className="prop-ref-actions-row" style={{ marginTop: '14px' }}>
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
                            onClick={() => setActiveTab('overview')}
                        >
                            Overview
                        </button>
                    </div>
                </div>
            )}

            {/* ============================================================== */}
            {/* FLOOR PLAN TAB                                                 */}
            {/* ============================================================== */}
            {activeTab === 'floorplan' && (
                <div className="prop-tab-content-panel animate-fade-in">
                    <div className="prop-specs-header-row">
                        <button
                            type="button"
                            className="prop-back-to-overview-btn"
                            onClick={() => setActiveTab('overview')}
                        >
                            ‹ Back to Overview
                        </button>
                        <span className="prop-specs-title-tag">Architectural Layout</span>
                    </div>

                    <div className="prop-floorplan-box">
                        <FloorPlanSvg bhk={bhkNum} />
                    </div>

                    <div className="prop-floorplan-details">
                        <h4 className="prop-floorplan-subtitle">Documented Room Dimensions</h4>
                        <ul className="prop-ref-details-list">
                            {roomTiles.map((t) => (
                                <li key={t.id} className="prop-ref-details-item">
                                    <strong style={{ color: '#38bdf8' }}>{t.name}:</strong> {t.dimension} ({t.spec})
                                </li>
                            ))}
                        </ul>
                    </div>

                    <div className="prop-primary-action-wrap" style={{ marginTop: '12px' }}>
                        <button
                            type="button"
                            className="prop-view-specs-primary-btn"
                            onClick={() => setActiveTab('specifications')}
                        >
                            View Visual Tiles ➔
                        </button>
                    </div>
                </div>
            )}

            {/* ============================================================== */}
            {/* IMAGES TAB                                                     */}
            {/* ============================================================== */}
            {activeTab === 'images' && (
                <div className="prop-tab-content-panel animate-fade-in">
                    <div className="prop-specs-header-row">
                        <button
                            type="button"
                            className="prop-back-to-overview-btn"
                            onClick={() => setActiveTab('overview')}
                        >
                            ‹ Back to Overview
                        </button>
                        <span className="prop-specs-title-tag">Gallery ({heroImages.length + 3} Photos)</span>
                    </div>

                    <div className="prop-gallery-grid">
                        {roomTiles.map((t, idx) => (
                            <div
                                key={idx}
                                className="prop-gallery-item"
                                onClick={() => handleTileClick(t)}
                            >
                                {t.imageUrl && resolveImgUrl ? (
                                    <img
                                        src={resolveImgUrl(t.imageUrl)}
                                        alt={t.name}
                                        className="prop-gallery-thumb"
                                        loading="lazy"
                                    />
                                ) : t.id === 'living' ? (
                                    <LivingRoomSvg />
                                ) : t.id === 'kitchen' ? (
                                    <KitchenSvg />
                                ) : t.id === 'balcony' ? (
                                    <BalconySvg />
                                ) : (
                                    <ApartmentIllustration />
                                )}
                                <span className="prop-gallery-badge">{t.name}</span>
                            </div>
                        ))}
                    </div>

                    <div className="prop-ref-actions-row" style={{ marginTop: '12px' }}>
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
                            onClick={() => setActiveTab('overview')}
                        >
                            Overview
                        </button>
                    </div>
                </div>
            )}

            {/* ============================================================== */}
            {/* VIRTUAL TOUR TAB                                               */}
            {/* ============================================================== */}
            {activeTab === 'virtualtour' && (
                <div className="prop-tab-content-panel animate-fade-in">
                    <div className="prop-specs-header-row">
                        <button
                            type="button"
                            className="prop-back-to-overview-btn"
                            onClick={() => setActiveTab('overview')}
                        >
                            ‹ Back to Overview
                        </button>
                        <span className="prop-specs-title-tag">360° Virtual Walkthrough</span>
                    </div>

                    <div className="prop-floorplan-box">
                        <VirtualTourSvg />
                    </div>

                    <div className="prop-primary-action-wrap" style={{ marginTop: '12px' }}>
                        <button
                            type="button"
                            className="prop-view-specs-primary-btn"
                            onClick={() => {
                                if (onImageClick && resolveImgUrl) {
                                    onImageClick({
                                        url: resolveImgUrl('/api/assets/images/Bedroom.jpg'),
                                        title: `360° Walkthrough — ${configTitle}`,
                                        category: 'VIRTUAL TOUR',
                                        project: title,
                                    });
                                }
                            }}
                        >
                            Launch 360° Fullscreen Viewer ➔
                        </button>
                    </div>
                </div>
            )}

            {/* ============================================================== */}
            {/* AMENITIES TAB                                                  */}
            {/* ============================================================== */}
            {activeTab === 'amenities' && (
                <div className="prop-tab-content-panel animate-fade-in">
                    <div className="prop-specs-header-row">
                        <button
                            type="button"
                            className="prop-back-to-overview-btn"
                            onClick={() => setActiveTab('overview')}
                        >
                            ‹ Back to Overview
                        </button>
                        <span className="prop-specs-title-tag">Project Amenities</span>
                    </div>

                    <div className="prop-amenities-grid">
                        {amenitiesList.map((amenity, aIdx) => (
                            <div key={aIdx} className="prop-amenity-card">
                                <span className="prop-amenity-icon">✓</span>
                                <span className="prop-amenity-name">{amenity}</span>
                            </div>
                        ))}
                    </div>

                    <div className="prop-ref-actions-row" style={{ marginTop: '14px' }}>
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
                            onClick={() => setActiveTab('overview')}
                        >
                            Overview
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
