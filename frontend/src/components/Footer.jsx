export default function Footer() {
  const year = new Date().getFullYear();

  return (
    <footer style={{
      borderTop: '1px solid var(--card-border)',
      background: 'color-mix(in srgb, var(--bg) 80%, transparent)',
      padding: '1.5rem 2rem',
      marginTop: '3rem',
    }}>
      <div style={{
        maxWidth: 1200,
        margin: '0 auto',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: '1rem',
        flexWrap: 'wrap',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '1.1rem' }}>🧠</span>
          <span style={{ fontWeight: 700, fontSize: '0.95rem' }}>StudyMind AI</span>
          <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            © {year} All rights reserved.
          </span>
        </div>

        <div style={{ display: 'flex', gap: '1.25rem', fontSize: '0.85rem' }}>
          {['Terms of Service', 'Privacy Policy', 'Help & Support'].map(label => (
            <a
              key={label}
              href="#"
              onClick={e => e.preventDefault()}
              style={{ color: 'var(--text-secondary)', textDecoration: 'none' }}
              onMouseEnter={e => { e.currentTarget.style.color = 'var(--text)'; }}
              onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-secondary)'; }}
            >
              {label}
            </a>
          ))}
        </div>

        <div style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.45rem',
          fontSize: '0.82rem',
          color: 'var(--text-secondary)',
          background: 'var(--card-bg)',
          border: '1px solid var(--card-border)',
          borderRadius: 20,
          padding: '0.35rem 0.9rem',
        }}>
          <span style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: '#10b981',
            boxShadow: '0 0 6px rgba(16,185,129,0.7)',
          }} />
          All systems operational
        </div>
      </div>
    </footer>
  );
}