import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useUi } from '../context/UiContext';
import { fetchPendingCount } from '../api';
import { TIER_LABELS, avatarEmoji } from '../constants';

function ThemeToggle() {
  const [theme, setTheme] = useState(
    () => localStorage.getItem('theme') || 'dark'
  );

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  return (
    <button
      onClick={() => setTheme(t => (t === 'dark' ? 'light' : 'dark'))}
      title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      aria-label="Toggle color theme"
      style={{
        background: 'var(--card-bg)',
        border: '1px solid var(--card-border)',
        borderRadius: 10,
        padding: '0.45rem 0.65rem',
        fontSize: '1rem',
        cursor: 'pointer',
        lineHeight: 1,
      }}
    >
      {theme === 'dark' ? '☀️' : '🌙'}
    </button>
  );
}

const navLinkStyle = ({ isActive }) => ({
  color: isActive ? 'var(--text)' : 'var(--text-secondary)',
  textDecoration: 'none',
  fontSize: '0.9rem',
  fontWeight: isActive ? 700 : 500,
  padding: '0.4rem 0.75rem',
  borderRadius: 8,
  background: isActive ? 'var(--card-bg)' : 'transparent',
  border: isActive ? '1px solid var(--card-border)' : '1px solid transparent',
});

export default function Navbar() {
  const { user, loading, logout } = useAuth();
  const { openSocial } = useUi();
  const [menuOpen, setMenuOpen] = useState(false);
  const [counts, setCounts] = useState({ total: 0 });
  const menuRef = useRef(null);
  const navigate = useNavigate();

  // Poll pending requests + duels for the bell badge.
  useEffect(() => {
    if (!user) {
      setCounts({ total: 0 });
      return undefined;
    }
    let cancelled = false;
    const tick = () => {
      fetchPendingCount()
        .then(d => { if (!cancelled) setCounts(d); })
        .catch(() => {});
    };
    tick();
    const id = setInterval(tick, 20000);
    return () => { cancelled = true; clearInterval(id); };
  }, [user]);

  // Close the dropdown on outside click
  useEffect(() => {
    const onClick = e => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  const handleLogout = async () => {
    setMenuOpen(false);
    await logout();
    navigate('/');
  };

  return (
    <header style={{
      borderBottom: '1px solid var(--card-border)',
      background: 'color-mix(in srgb, var(--bg) 80%, transparent)',
      backdropFilter: 'blur(12px)',
      padding: '0.85rem 2rem',
      position: 'sticky',
      top: 0,
      zIndex: 50,
    }}>
      <nav style={{
        maxWidth: 1200,
        margin: '0 auto',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: '1rem',
        flexWrap: 'wrap',
      }}>
        {/* Brand */}
        <Link to="/" style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.6rem',
          textDecoration: 'none',
          color: 'var(--text)',
          fontWeight: 800,
          fontSize: '1.2rem',
        }}>
          🧠 <span>StudyMind AI</span>
        </Link>

        {/* Nav links */}
        <div style={{ display: 'flex', gap: '0.35rem', alignItems: 'center' }}>
          <NavLink to="/" style={navLinkStyle} end>PDF Workspace</NavLink>
          <NavLink to="/quiz" style={navLinkStyle}>Daily Quiz</NavLink>
          <NavLink to="/leaderboard" style={navLinkStyle}>Leaderboards</NavLink>
        </div>

        {/* Right side */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <ThemeToggle />

          {loading ? (
            <span style={{
              width: 20, height: 20,
              border: '2px solid rgba(99,102,241,0.3)',
              borderTopColor: '#6366f1',
              borderRadius: '50%',
              animation: 'spin 0.8s linear infinite',
              display: 'inline-block',
            }} />
          ) : user ? (
            <>
              {/* Social bell — friend requests + duels */}
              <div style={{ position: 'relative' }}>
                <button
                  onClick={() => openSocial('requests')}
                  aria-label="Friends and duels"
                  title="Friends & duels"
                  style={{
                    background: 'var(--card-bg)',
                    border: '1px solid var(--card-border)',
                    borderRadius: 10,
                    padding: '0.45rem 0.6rem',
                    fontSize: '1rem',
                    cursor: 'pointer',
                    lineHeight: 1,
                    position: 'relative',
                  }}
                >
                  🔔
                </button>
                {counts.total > 0 && (
                  <span style={{
                    position: 'absolute', top: -6, right: -6,
                    minWidth: 18, height: 18, borderRadius: 10,
                    background: '#ef4444', color: '#fff',
                    fontSize: '0.68rem', fontWeight: 800,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    padding: '0 4px',
                    border: '2px solid var(--bg)',
                  }}>
                    {counts.total > 9 ? '9+' : counts.total}
                  </span>
                )}
              </div>

              {/* Streak badge */}
              <span title="Daily streak" style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.35rem',
                background: 'rgba(251,146,60,0.12)',
                border: '1px solid rgba(251,146,60,0.35)',
                color: '#fdba74',
                borderRadius: 20,
                padding: '0.3rem 0.8rem',
                fontSize: '0.85rem',
                fontWeight: 700,
              }}>
                🔥 {user.current_streak}
              </span>

              {/* Avatar dropdown */}
              <div ref={menuRef} style={{ position: 'relative' }}>
                <button
                  onClick={() => setMenuOpen(o => !o)}
                  aria-label="Account menu"
                  style={{
                    width: 40,
                    height: 40,
                    borderRadius: '50%',
                    background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                    border: '2px solid var(--card-border)',
                    fontSize: '1.15rem',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  {avatarEmoji(user.avatar)}
                </button>

                {menuOpen && (
                  <div style={{
                    position: 'absolute',
                    right: 0,
                    top: 'calc(100% + 0.6rem)',
                    minWidth: 220,
                    background: 'var(--card-bg-solid)',
                    border: '1px solid var(--card-border)',
                    borderRadius: 14,
                    boxShadow: 'var(--shadow)',
                    padding: '0.75rem',
                    zIndex: 100,
                  }}>
                    <div style={{
                      padding: '0.5rem 0.6rem 0.75rem',
                      borderBottom: '1px solid var(--card-border)',
                      marginBottom: '0.5rem',
                    }}>
                      <div style={{ fontWeight: 700, fontSize: '0.95rem' }}>
                        {avatarEmoji(user.avatar)} {user.username}
                      </div>
                      <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', marginTop: '0.15rem' }}>
                        🎯 {TIER_LABELS[user.gk_skill_tier] || user.gk_skill_tier || 'Intermediate'}
                      </div>
                    </div>
                    <Link
                      to="/profile"
                      onClick={() => setMenuOpen(false)}
                      style={{
                        display: 'block',
                        padding: '0.55rem 0.6rem',
                        borderRadius: 8,
                        color: 'var(--text)',
                        textDecoration: 'none',
                        fontSize: '0.9rem',
                      }}
                      onMouseEnter={e => { e.currentTarget.style.background = 'var(--card-bg)'; }}
                      onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
                    >
                      👤 My Profile
                    </Link>
                    <button
                      onClick={handleLogout}
                      style={{
                        width: '100%',
                        textAlign: 'left',
                        background: 'none',
                        border: 'none',
                        borderRadius: 8,
                        padding: '0.55rem 0.6rem',
                        color: '#f87171',
                        fontSize: '0.9rem',
                        cursor: 'pointer',
                      }}
                      onMouseEnter={e => { e.currentTarget.style.background = 'rgba(239,68,68,0.1)'; }}
                      onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
                    >
                      ⎋ Log Out
                    </button>
                  </div>
                )}
              </div>
            </>
          ) : (
            <>
              <Link to="/login" style={{
                color: 'var(--text)',
                textDecoration: 'none',
                fontSize: '0.9rem',
                fontWeight: 600,
                padding: '0.5rem 1rem',
                border: '1px solid var(--card-border)',
                borderRadius: 10,
                background: 'var(--card-bg)',
              }}>
                Log In
              </Link>
              <Link to="/signup" style={{
                color: '#fff',
                textDecoration: 'none',
                fontSize: '0.9rem',
                fontWeight: 700,
                padding: '0.5rem 1.1rem',
                borderRadius: 10,
                background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              }}>
                Get Started
              </Link>
            </>
          )}
        </div>
      </nav>
    </header>
  );
}