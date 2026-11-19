import React from 'react';

/**
 * Lightweight Markdown renderer for Real Estate chat responses.
 * Parses headers, bold, italics, inline code/dimensions, bullet lists, numbered lists, and tables.
 */
export default function MarkdownRenderer({ content }) {
    if (!content) return null;

    // Helper to format inline styling (bold, italic, dimension tags, inline code)
    const renderInline = (text) => {
        if (!text) return text;

        // Split by code/dimension backticks `...`
        const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g);

        return parts.map((part, index) => {
            if (part.startsWith('`') && part.endsWith('`')) {
                return (
                    <code key={index} className="inline-dimension">
                        {part.slice(1, -1)}
                    </code>
                );
            }
            if (part.startsWith('**') && part.endsWith('**')) {
                return (
                    <strong key={index} className="md-bold">
                        {part.slice(2, -2)}
                    </strong>
                );
            }
            if (part.startsWith('*') && part.endsWith('*')) {
                return <em key={index}>{part.slice(1, -1)}</em>;
            }
            return part;
        });
    };

    // Parse block-level elements
    const lines = content.split('\n');
    const elements = [];
    let i = 0;

    while (i < lines.length) {
        const line = lines[i];
        const trimmed = line.trim();

        // 1. Table Detection (| Header 1 | Header 2 |)
        if (trimmed.startsWith('|') && trimmed.endsWith('|') && lines[i + 1] && lines[i + 1].includes('---')) {
            const tableRows = [];
            while (i < lines.length && lines[i].trim().startsWith('|') && lines[i].trim().endsWith('|')) {
                tableRows.push(lines[i].trim());
                i++;
            }

            const headerCols = tableRows[0]
                .split('|')
                .slice(1, -1)
                .map((c) => c.trim());

            // Skip separator line (tableRows[1])
            const bodyRows = tableRows.slice(2).map((row) =>
                row
                    .split('|')
                    .slice(1, -1)
                    .map((c) => c.trim())
            );

            elements.push(
                <div key={`table-${elements.length}`} className="md-table-wrapper">
                    <table className="md-table">
                        <thead>
                            <tr>
                                {headerCols.map((col, idx) => (
                                    <th key={idx}>{renderInline(col)}</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {bodyRows.map((row, rIdx) => (
                                <tr key={rIdx}>
                                    {row.map((cell, cIdx) => (
                                        <td key={cIdx}>{renderInline(cell)}</td>
                                    ))}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            );
            continue;
        }

        // 2. Headers (#, ##, ###)
        if (trimmed.startsWith('### ')) {
            elements.push(
                <h4 key={`h4-${elements.length}`} className="md-h4">
                    {renderInline(trimmed.slice(4))}
                </h4>
            );
            i++;
            continue;
        }
        if (trimmed.startsWith('## ')) {
            elements.push(
                <h3 key={`h3-${elements.length}`} className="md-h3">
                    {renderInline(trimmed.slice(3))}
                </h3>
            );
            i++;
            continue;
        }
        if (trimmed.startsWith('# ')) {
            elements.push(
                <h2 key={`h2-${elements.length}`} className="md-h2">
                    {renderInline(trimmed.slice(2))}
                </h2>
            );
            i++;
            continue;
        }

        // 3. Bullet list items (* or - or •)
        if (trimmed.startsWith('• ') || trimmed.startsWith('* ') || trimmed.startsWith('- ')) {
            const listItems = [];
            while (
                i < lines.length &&
                (lines[i].trim().startsWith('• ') ||
                    lines[i].trim().startsWith('* ') ||
                    lines[i].trim().startsWith('- '))
            ) {
                const itemText = lines[i].trim().replace(/^[•*-]\s+/, '');
                listItems.push(itemText);
                i++;
            }
            elements.push(
                <ul key={`ul-${elements.length}`} className="md-list">
                    {listItems.map((item, idx) => (
                        <li key={idx}>{renderInline(item)}</li>
                    ))}
                </ul>
            );
            continue;
        }

        // 4. Numbered list items (1. , 2. )
        if (/^\d+\.\s+/.test(trimmed)) {
            const numItems = [];
            while (i < lines.length && /^\d+\.\s+/.test(lines[i].trim())) {
                const itemText = lines[i].trim().replace(/^\d+\.\s+/, '');
                numItems.push(itemText);
                i++;
            }
            elements.push(
                <ol key={`ol-${elements.length}`} className="md-ordered-list">
                    {numItems.map((item, idx) => (
                        <li key={idx}>{renderInline(item)}</li>
                    ))}
                </ol>
            );
            continue;
        }

        // 5. Empty line (Paragraph separator)
        if (trimmed === '') {
            i++;
            continue;
        }

        // 6. Regular Paragraph
        elements.push(
            <p key={`p-${elements.length}`} className="md-paragraph">
                {renderInline(line)}
            </p>
        );
        i++;
    }

    return <div className="markdown-body">{elements}</div>;
}
