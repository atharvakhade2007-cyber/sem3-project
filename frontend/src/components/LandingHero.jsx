import { Link } from 'react-router-dom';

export default function LandingHero() {
  return (
    <div style={{
      maxWidth: 700, margin: '3rem auto', textAlign: 'center', padding: '0 1.5rem',
    }}>
      <div style={{ fontSize: '4rem', marginBottom: '1rem' }}>🎓</div>
      <h1 style={{ fontSize: '2.4rem', fontWeight: 800, marginBottom: '0.75rem' }}>
        AI-Powered Study Companion
      </h1>
      <p style={{ color: 'var(--text-secondary)', fontSize: '1.05rem', lineHeight: 1.6, marginBottom: '2rem' }}>
        Upload a PDF to unlock intelligent study tools — summaries, flashcards,
        and adaptive testing — plus a daily GK quiz with global leaderboards.
        Sign in to start learning.
      </p>
      <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap' }}>
        <Link to="/login" style={{
          background: 'var(--card-bg)', border: '1px solid var(--card-border)',
          color: 'var(--text)', textDecoration: 'none',
          borderRadius: 12, padding: '0.8rem 2rem', fontWeight: 700,
        }}>
          Log In
        </Link>
        <Link to="/signup" style={{
          background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
          color: '#fff', textDecoration: 'none',
          borderRadius: 12, padding: '0.8rem 2rem', fontWeight: 700,
          boxShadow: '0 4px 18px rgba(99,102,241,0.4)',
        }}>
          Get Started — It's Free
        </Link>
      </div>
      <div style={{
        display: 'inline-flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap',
        marginTop: '2.5rem',
      }}>
        {['📄 Smart Summary', '🃏 Flashcards', '📈 Adaptive Test', '🗓️ Daily Quiz'].map(label => (
          <span key={label} style={{
            background: 'var(--card-bg)', border: '1px solid var(--card-border)',
            color: 'var(--text-secondary)', padding: '0.5rem 1rem', borderRadius: 20, fontSize: '0.85rem',
          }}>
            ✅ {label}
          </span>
        ))}
      </div>
    </div>
  );
}
