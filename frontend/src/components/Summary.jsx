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
      <div style={{ textAlign: 'center', padding: '4rem', color: '#94a3b8' }}>
        <div style={{
          display: 'inline-block', width: 40, height: 40,
          border: '4px solid rgba(255,255,255,0.15)', borderRadius: '50%',
          borderTopColor: '#6366f1', animation: 'spin 0.8s linear infinite',
          marginBottom: '1rem',
        }} />
        <p>Generating summary...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ textAlign: 'center', padding: '4rem', color: '#ef4444' }}>
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
      <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.5rem' }}>
        <button onClick={copyMarkdown} style={{
          padding: '0.6rem 1.25rem', borderRadius: 8, border: '1px solid rgba(255,255,255,0.1)',
          background: '#6366f1', color: 'white', fontWeight: 500, fontSize: '0.85rem', cursor: 'pointer',
        }}>
          📋 Copy Markdown
        </button>
      </div>

      {/* Executive Summary */}
      <div style={{ marginBottom: '2rem' }}>
        <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#94a3b8', marginBottom: '0.75rem' }}>
          ⚡ TL;DR
        </h3>
        <div style={{ lineHeight: 1.7, color: '#cbd5e1', fontSize: '1rem' }}>
          {data.executive_summary}
        </div>
      </div>

      {/* Key Concepts */}
      <div style={{ marginBottom: '2rem' }}>
        <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#94a3b8', marginBottom: '0.75rem' }}>
          💡 Key Concepts
        </h3>
        <ul style={{ listStyle: 'none' }}>
          {data.key_concepts?.map((concept, i) => (
            <li key={i} style={{ padding: '0.5rem 0', borderBottom: '1px solid rgba(255,255,255,0.05)', fontSize: '0.9rem', color: '#cbd5e1' }}>
              {concept}
            </li>
          ))}
        </ul>
      </div>

      {/* Terminology */}
      <div>
        <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#94a3b8', marginBottom: '0.75rem' }}>
          📖 Terminology
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1rem' }}>
          {data.terminology?.map((term, i) => (
            <div key={i} style={{
              background: 'rgba(15,23,42,0.6)', border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 10, padding: '1rem',
            }}>
              <div style={{ fontWeight: 700, color: '#8b5cf6', marginBottom: '0.25rem' }}>{term.term}</div>
              <div style={{ fontSize: '0.85rem', color: '#cbd5e1', lineHeight: 1.5 }}>{term.definition}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
