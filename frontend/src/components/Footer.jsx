export default function Footer() {
  const year = new Date().getFullYear();

  return (
    <footer
      style={{
        borderTop: '1px solid var(--card-border)',
        background: 'color-mix(in srgb, var(--bg) 78%, transparent)',
        padding: '1.75rem 2rem',
        marginTop: '4rem',
      }}
    >
      <div
        style={{
          maxWidth: 1200,
          margin: '0 auto',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '1rem',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '1rem' }}>🧠</span>
          <span style={{ fontWeight: 650, fontSize: '0.92rem', letterSpacing: '-0.01em' }}>
            StudyMind AI
          </span>
          <span style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>
            © {year}
          </span>
        </div>

        <div style={{ display: 'flex', gap: '1.4rem', fontSize: '0.83rem' }}>
          {['Terms of Service', 'Privacy Policy', 'Help & Support'].map(label => (
            <a
              key={label}
              href="#"
              onClick={e => e.preventDefault()}
              style={{ color: 'var(--text-secondary)', textDecoration: 'none', transition: 'color 0.2s ease' }}
              onMouseEnter={e => { e.currentTarget.style.color = 'var(--text)'; }}
              onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-secondary)'; }}
            >
              {label}
            </a>
          ))}
        </div>

        <div
          className="pill"
          style={{ fontSize: '0.78rem', padding: '0.3rem 0.8rem' }}
        >
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: '50%',
              background: 'var(--success)',
            }}
          />
          All systems operational
        </div>
      </div>
    </footer>
  );
}
