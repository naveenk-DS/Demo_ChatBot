import React, { useState } from 'react';

/**
 * Collapsible RAG Sources & Citation card component.
 * Displays retrieved PDF document names, page numbers, categories, and fusion scores.
 */
export default function SourceCard({ sources }) {
    const [open, setOpen] = useState(false);

    if (!sources || sources.length === 0) return null;

    return (
        <div className="sources-container">
            <button
                type="button"
                className="sources-toggle-btn"
                onClick={() => setOpen(!open)}
                aria-expanded={open}
            >
                <span className="sources-icon">📄</span>
                <span className="sources-label">
                    {sources.length} Verified Document Source{sources.length > 1 ? 's' : ''}
                </span>
                <span className="sources-chevron">{open ? '▲' : '▼'}</span>
            </button>

            {open && (
                <div className="sources-list animate-slide-down">
                    <div className="sources-header">
                        <small className="sources-pipeline-tag">
                            Hybrid Retrieval: Dense (nomic-embed-text) + BM25 Okapi + RRF (k=60)
                        </small>
                    </div>
                    {sources.map((s, idx) => (
                        <div key={idx} className="source-item">
                            <div className="source-item-top">
                                <span className="source-filename">
                                    {s.source || 'Property Document.pdf'}
                                </span>
                                <span className="source-page-badge">Page {s.page || 1}</span>
                            </div>
                            <div className="source-meta-row">
                                {s.configuration && (
                                    <span className="source-meta-tag config-tag">
                                        {s.configuration}
                                    </span>
                                )}
                                {s.category && (
                                    <span className="source-meta-tag category-tag">
                                        {s.category.replace('_', ' ')}
                                    </span>
                                )}
                                {s.chunk_id && (
                                    <span className="source-meta-tag chunk-tag" title={s.chunk_id}>
                                        Chunk: {s.chunk_id.split('_').slice(-2).join('_')}
                                    </span>
                                )}
                                {s.rrf_score && (
                                    <span className="source-meta-tag score-tag" title="Reciprocal Rank Fusion Score">
                                        RRF: {Number(s.rrf_score).toFixed(4)}
                                    </span>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
