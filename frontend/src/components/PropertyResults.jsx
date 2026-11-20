import React, { useState } from 'react';
import PropertyCard from './PropertyCard';

/**
 * Matching property results showcase panel.
 * Displays retrieved Athena SQL inventory records, or context-aware
 * local image asset gallery filtered by user requests (room/category/all).
 */
export default function PropertyResults({
    properties = [],
    imageAssets = [],
    allImageAssets = [],
    imageFilter = null,
    onResetImageFilter,
    apiBaseUrl = '',
    onSelectProperty,
    onClose
}) {
    const [selectedImage, setSelectedImage] = useState(null);

    const resolveImageUrl = (url) => {
        if (!url) return '';
        if (url.startsWith('http://') || url.startsWith('https://')) {
            return url;
        }
        const base = apiBaseUrl.replace(/\/+$/, '');
        const path = url.startsWith('/') ? url : `/${url}`;
        return base ? `${base}${path}` : path;
    };

    // State 1: Matching property inventory records found
    if (properties && properties.length > 0) {
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

    // State 2: User specifically requested an image category, but NO matching images exist
    // Strictly adhere to: "Do not show unrelated images as fallback when the user specifically requests a category"
    if (imageFilter && imageFilter.active && (!imageAssets || imageAssets.length === 0)) {
        const catName = imageFilter.category || 'Requested';
        const totalCount = allImageAssets.length || imageFilter.total_available || 0;
        return (
            <div className="property-results-panel has-gallery">
                <div className="panel-header">
                    <div>
                        <h2 className="panel-title">Property Media Assets</h2>
                        <p className="panel-subtitle">Filter: {catName}</p>
                    </div>
                    <span className="results-count-pill empty-count-pill">0 Images</span>
                </div>

                <div className="image-gallery-scroll">
                    <div className="category-empty-state">
                        <div className="category-empty-icon">🖼️</div>
                        <h3 className="category-empty-title">
                            No {catName.toUpperCase()} Images Available
                        </h3>
                        <p className="category-empty-text">
                            No local image files match the requested category <strong>"{catName}"</strong> in this project's assets.
                        </p>

                        {imageFilter.available_categories && imageFilter.available_categories.length > 0 && (
                            <div className="available-categories-card">
                                <span className="available-label">Available categories in project assets:</span>
                                <div className="available-category-chips">
                                    {imageFilter.available_categories.map((c) => (
                                        <span key={c} className="available-category-chip">
                                            {c}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        )}

                        {onResetImageFilter && (
                            <button
                                type="button"
                                className="btn-reset-gallery"
                                onClick={onResetImageFilter}
                            >
                                View All Property Images {totalCount > 0 ? `(${totalCount})` : ''}
                            </button>
                        )}
                    </div>
                </div>
            </div>
        );
    }

    // State 3: Local image assets available to display (only when image mode was explicitly activated)
    if (imageFilter && imageFilter.active && imageAssets && imageAssets.length > 0) {
        const isFiltered = !imageFilter.is_all;
        const totalCount = allImageAssets.length || imageFilter?.total_available || imageAssets.length;

        return (
            <div className="property-results-panel has-gallery">
                <div className="panel-header">
                    <div>
                        <h2 className="panel-title">Property Media Assets</h2>
                        <p className="panel-subtitle">
                            {isFiltered
                                ? `Showing ${imageFilter.category} media`
                                : 'Available project photos & layout references'}
                        </p>
                    </div>
                    <div className="panel-header-pills">
                        <span className="results-count-pill assets-count-pill">
                            {imageAssets.length} Image{imageAssets.length > 1 ? 's' : ''}
                        </span>
                    </div>
                </div>

                <div className="image-gallery-scroll">
                    {/* Filter Active Bar */}
                    {isFiltered ? (
                        <div className="gallery-filter-bar">
                            <div className="filter-bar-info">
                                <span className="filter-active-dot">●</span>
                                <span>
                                    Category: <strong>{imageFilter.category}</strong> ({imageAssets.length})
                                </span>
                            </div>
                            {onResetImageFilter && (
                                <button
                                    type="button"
                                    className="btn-show-all-link"
                                    onClick={onResetImageFilter}
                                    title="Show all available project images"
                                >
                                    Show all ({totalCount})
                                </button>
                            )}
                        </div>
                    ) : (
                        <div className="image-gallery-notice">
                            <span className="notice-icon">📷</span>
                            <div className="notice-content">
                                <strong>Project Media Gallery</strong>
                                <p>Showing verified local photographs. Ask for specific areas (e.g. <em>"Show bathroom images"</em>):</p>
                            </div>
                        </div>
                    )}

                    <div className="image-gallery-grid">
                        {imageAssets.map((asset, idx) => {
                            const fullUrl = resolveImageUrl(asset.url);
                            return (
                                <div
                                    key={asset.filename || idx}
                                    className="gallery-thumbnail-card"
                                    onClick={() => setSelectedImage(asset)}
                                    role="button"
                                    tabIndex={0}
                                    onKeyDown={(e) => {
                                        if (e.key === 'Enter' || e.key === ' ') {
                                            setSelectedImage(asset);
                                        }
                                    }}
                                    title="Click to view full image"
                                >
                                    <div className="thumbnail-wrapper">
                                        <img
                                            src={fullUrl}
                                            alt={asset.filename}
                                            loading="lazy"
                                            onError={(e) => {
                                                e.target.style.display = 'none';
                                                e.target.parentElement.classList.add('img-failed');
                                            }}
                                        />
                                        <span className="zoom-hint-badge">🔍 Click to zoom</span>
                                    </div>
                                    <div className="thumbnail-info">
                                        <div className="thumbnail-header-row">
                                            {asset.category && (
                                                <span className="thumbnail-category-pill">
                                                    {asset.category}
                                                </span>
                                            )}
                                            {asset.property_name && (
                                                <span className="thumbnail-property-tag">
                                                    {asset.property_name}
                                                </span>
                                            )}
                                        </div>
                                        <span className="thumbnail-filename" title={asset.filename}>
                                            {asset.filename}
                                        </span>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>

                {/* Modal for full image preview */}
                {selectedImage && (
                    <div
                        className="image-preview-overlay"
                        onClick={() => setSelectedImage(null)}
                        role="dialog"
                        aria-modal="true"
                    >
                        <div
                            className="image-preview-dialog"
                            onClick={(e) => e.stopPropagation()}
                        >
                            <div className="image-preview-header">
                                <div className="preview-title-group">
                                    <h3 className="preview-title">{selectedImage.filename}</h3>
                                    {selectedImage.category && (
                                        <span className="thumbnail-category-pill">
                                            {selectedImage.category}
                                        </span>
                                    )}
                                </div>
                                <button
                                    type="button"
                                    className="image-preview-close"
                                    onClick={() => setSelectedImage(null)}
                                    aria-label="Close image preview"
                                >
                                    ✕
                                </button>
                            </div>
                            <div className="image-preview-body">
                                <img
                                    src={resolveImageUrl(selectedImage.url)}
                                    alt={selectedImage.filename}
                                    className="image-preview-img"
                                />
                            </div>
                            <div className="image-preview-footer">
                                <span className="preview-asset-note">
                                    📁 Stored as project media asset • Plain image file mode
                                </span>
                                {selectedImage.property_name && (
                                    <span className="preview-property-note">
                                        Project: <strong>{selectedImage.property_name}</strong>
                                    </span>
                                )}
                            </div>
                        </div>
                    </div>
                )}
            </div>
        );
    }

    // State 4: Neither properties nor images exist -> Standard empty state
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
