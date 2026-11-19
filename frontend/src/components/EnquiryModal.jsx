import React from 'react';

/**
 * Interactive customer enquiry modal for scheduling site visits or contacting agents.
 */
export default function EnquiryModal({
    selectedProperty,
    form,
    setForm,
    onSubmit,
    onClose,
    isSubmitting,
}) {
    if (!selectedProperty) return null;

    return (
        <div className="modal-overlay animate-fade-in" onClick={onClose}>
            <div
                className="modal-card animate-scale-up"
                onClick={(e) => e.stopPropagation()}
            >
                <button
                    type="button"
                    className="modal-close-btn"
                    onClick={onClose}
                    aria-label="Close modal"
                >
                    ×
                </button>

                <div className="modal-header">
                    <span className="modal-badge">Site Visit & Enquiry</span>
                    <h3 className="modal-title">Connect with Property Specialist</h3>
                    <p className="modal-subtitle">
                        Interested in Property Ref:{' '}
                        <strong>{selectedProperty.property_id || 'Selected Unit'}</strong>
                        {selectedProperty.location && ` (${selectedProperty.location})`}
                    </p>
                </div>

                <form className="modal-form" onSubmit={onSubmit}>
                    <div className="form-group">
                        <label htmlFor="enquiry-name">Full Name *</label>
                        <input
                            id="enquiry-name"
                            type="text"
                            required
                            placeholder="e.g. John Doe"
                            value={form.name}
                            onChange={(e) => setForm({ ...form, name: e.target.value })}
                        />
                    </div>

                    <div className="form-group">
                        <label htmlFor="enquiry-phone">Phone Number *</label>
                        <input
                            id="enquiry-phone"
                            type="tel"
                            required
                            placeholder="+91 98765 43210"
                            value={form.phone}
                            onChange={(e) => setForm({ ...form, phone: e.target.value })}
                        />
                    </div>

                    <div className="form-group">
                        <label htmlFor="enquiry-message">Your Message / Questions</label>
                        <textarea
                            id="enquiry-message"
                            rows={3}
                            required
                            placeholder="I would like to schedule a site visit and receive pricing details."
                            value={form.message}
                            onChange={(e) => setForm({ ...form, message: e.target.value })}
                        />
                    </div>

                    <div className="consent-checkbox-row">
                        <label className="consent-label">
                            <input
                                type="checkbox"
                                checked={form.consent}
                                onChange={(e) => setForm({ ...form, consent: e.target.checked })}
                            />
                            <span>
                                I agree to be contacted by the property specialist regarding this enquiry.
                            </span>
                        </label>
                    </div>

                    <div className="modal-actions">
                        <button
                            type="button"
                            className="btn-cancel"
                            onClick={onClose}
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            className="btn-submit"
                            disabled={!form.consent || !form.name.trim() || !form.phone.trim() || isSubmitting}
                        >
                            {isSubmitting ? 'Submitting...' : 'Submit Site Visit Request'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
