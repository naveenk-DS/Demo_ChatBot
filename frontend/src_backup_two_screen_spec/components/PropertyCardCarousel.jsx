import React, { useState, useRef } from 'react';
import PropertyDetailCard from './PropertyDetailCard';

/**
 * One-card-at-a-time Property Carousel.
 * - Displays exactly ONE complete property card at a time occupying 100% available message width.
 * - Previous / Next navigation controls with position indicator (e.g. "1 of 3").
 * - Smooth horizontal sliding transitions.
 * - Touch swipe support for mobile.
 * - Never crops or partially reveals adjacent cards.
 */
export default function PropertyCardCarousel({
    properties = [],
    currentTime,
    onSelectProperty,
    onSendBrochure,
    onImageClick,
    resolveImgUrl,
}) {
    const [currentIndex, setCurrentIndex] = useState(0);
    const touchStartXRef = useRef(null);
    const touchEndXRef = useRef(null);

    if (!properties || properties.length === 0) return null;

    const total = properties.length;
    const isMulti = total > 1;

    const handlePrev = (e) => {
        if (e) e.stopPropagation();
        setCurrentIndex((prev) => (prev > 0 ? prev - 1 : 0));
    };

    const handleNext = (e) => {
        if (e) e.stopPropagation();
        setCurrentIndex((prev) => (prev < total - 1 ? prev + 1 : total - 1));
    };

    // Touch swipe handling for mobile
    const handleTouchStart = (e) => {
        touchStartXRef.current = e.targetTouches[0].clientX;
        touchEndXRef.current = null;
    };

    const handleTouchMove = (e) => {
        touchEndXRef.current = e.targetTouches[0].clientX;
    };

    const handleTouchEnd = () => {
        if (touchStartXRef.current === null || touchEndXRef.current === null) return;
        const diffX = touchStartXRef.current - touchEndXRef.current;
        const minSwipeDistance = 45; // Threshold in px

        if (diffX > minSwipeDistance && currentIndex < total - 1) {
            // Swiped Left -> Go Next
            setCurrentIndex((prev) => prev + 1);
        } else if (diffX < -minSwipeDistance && currentIndex > 0) {
            // Swiped Right -> Go Previous
            setCurrentIndex((prev) => prev - 1);
        }

        touchStartXRef.current = null;
        touchEndXRef.current = null;
    };

    return (
        <div className="prop-carousel-container">
            {/* Navigation Bar when 2 or more cards */}
            {isMulti && (
                <div className="prop-carousel-header">
                    <span className="prop-carousel-title">
                        Properties ({total})
                    </span>
                    <div className="prop-carousel-nav">
                        <button
                            type="button"
                            className="prop-carousel-btn"
                            onClick={handlePrev}
                            disabled={currentIndex === 0}
                            aria-label="Previous property"
                            title="Previous property"
                        >
                            ‹
                        </button>
                        <span className="prop-carousel-indicator">
                            {currentIndex + 1} of {total}
                        </span>
                        <button
                            type="button"
                            className="prop-carousel-btn"
                            onClick={handleNext}
                            disabled={currentIndex === total - 1}
                            aria-label="Next property"
                            title="Next property"
                        >
                            ›
                        </button>
                    </div>
                </div>
            )}

            {/* Carousel Viewport: Bounded to 100% width, hides any overflowing card */}
            <div
                className="prop-carousel-viewport"
                onTouchStart={handleTouchStart}
                onTouchMove={handleTouchMove}
                onTouchEnd={handleTouchEnd}
            >
                <div
                    className="prop-carousel-track"
                    style={{ transform: `translateX(-${currentIndex * 100}%)` }}
                >
                    {properties.map((prop, idx) => (
                        <div key={prop.property_id || idx} className="prop-carousel-slide">
                            <PropertyDetailCard
                                property={prop}
                                index={idx}
                                currentTime={currentTime}
                                onSelectProperty={onSelectProperty}
                                onSendBrochure={onSendBrochure}
                                onImageClick={onImageClick}
                                resolveImgUrl={resolveImgUrl}
                            />
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}

