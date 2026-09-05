import { useState, useEffect } from 'react';
import { generateSummary } from '../api';

export default function Summary({ documentId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function load() {
      try {
        const result = await generateSummary(documentId);
        setData(result.summary);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [documentId]);

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '4rem', color: 'var(--text-secondary)' }}>
        <div className="spinner" style={{ margin: '0 auto 1rem' }} />
        <p className="t-body">Generating summary...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ textAlign: 'center', padding: '4rem', color: 'var(--danger)' }}>
        <p>Error: {error}</p>
      </div>
    );
  }

  const copyMarkdown = () => {
    let md = `# Summary\n\n## TL;DR\n\n${data.executive_summary}\n\n## Key Concepts\n\n`;
    data.key_concepts?.forEach(c => { md += `- ${c}\n`; });
    md += `\n## Terminology\n\n`;
    data.terminology?.forEach(t => { md += `**${t.term}** — ${t.definition}\n\n`; });
    navigator.clipboard.writeText(md);
  };

  return (
    <div>
      <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.75rem' }}>
        <button onClick={copyMarkdown} className="btn btn-secondary" style={{ padding: '0.55rem 1.2rem', fontSize: '0.85rem' }}>
          📋 Copy Markdown
        </button>
      </div>

      {/* Executive Summary */}
      <div style={{ marginBottom: '2.25rem' }}>
        <h3 className="t-eyebrow" style={{ marginBottom: '0.8rem' }}>
          ⚡ TL;DR
        </h3>
        <div style={{ lineHeight: 1.7, fontSize: '1.05rem', letterSpacing: '-0.005em' }}>
          {data.executive_summary}
        </div>
      </div>

      {/* Key Concepts */}
      <div style={{ marginBottom: '2.25rem' }}>
        <h3 className="t-eyebrow" style={{ marginBottom: '0.8rem' }}>
          💡 Key Concepts
        </h3>
        <ul style={{ listStyle: 'none' }}>
          {data.key_concepts?.map((concept, i) => (
            <li
              key={i}
              style={{
                padding: '0.55rem 0',
                borderBottom: '1px solid var(--card-border)',
                fontSize: '0.92rem',
                lineHeight: 1.6,
              }}
            >
              {concept}
            </li>
          ))}
        </ul>
      </div>

      {/* Terminology */}
      <div>
        <h3 className="t-eyebrow" style={{ marginBottom: '0.8rem' }}>
          📖 Terminology
        </h3>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
            gap: '14px',
          }}
        >
          {data.terminology?.map((term, i) => (
            <div
              key={i}
              className="card card-hover"
              style={{ padding: '1.1rem 1.25rem', borderRadius: 'var(--radius-md)' }}
            >
              <div style={{ fontWeight: 650, color: 'var(--accent)', marginBottom: '0.3rem', fontSize: '0.95rem' }}>
                {term.term}
              </div>
              <div className="t-caption" style={{ lineHeight: 1.55 }}>
                {term.definition}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
