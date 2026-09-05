import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { BrainCircuit, Flame, Cloud, Bell, User, LogOut, Sun, Moon } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useUi } from '../context/UiContext';
import { fetchPendingCount } from '../api';
import { levelLabel, avatarEmoji } from '../constants';

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
      className="btn btn-secondary"
      style={{
        padding: '0.45rem 0.6rem',
        lineHeight: 1,
        borderRadius: 999,
        display: 'inline-flex',
      }}
    >
      {theme === 'dark'
        ? <Sun size={15} strokeWidth={2} />
        : <Moon size={15} strokeWidth={2} />}
    </button>
  );
}

const navLinkStyle = ({ isActive }) => ({
  color: isActive ? 'var(--text)' : 'var(--text-secondary)',
  textDecoration: 'none',
  fontSize: '0.88rem',
  fontWeight: isActive ? 650 : 500,
  padding: '0.42rem 0.9rem',
  borderRadius: 999,
  background: isActive ? 'var(--accent-soft)' : 'transparent',
  border: '1px solid transparent',
  transition: 'color 0.2s ease, background 0.2s ease',
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
    <header
      style={{
        borderBottom: '1px solid var(--card-border)',
        background: 'color-mix(in srgb, var(--bg) 72%, transparent)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        padding: '0.8rem 2rem',
        position: 'sticky',
        top: 0,
        zIndex: 50,
      }}
    >
      <nav
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
        {/* Brand */}
        <Link
          to="/"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.6rem',
            textDecoration: 'none',
            color: 'var(--text)',
            fontWeight: 700,
            fontSize: '1.12rem',
            letterSpacing: '-0.02em',
          }}
        >
          <span
            className="icon-tile icon-tile-gradient"
            style={{ width: 34, height: 34, borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          >
            <BrainCircuit size={19} strokeWidth={2} color="#fff" />
          </span>
          <span className="t-grad" style={{ fontWeight: 800 }}>
            AdaptiveQuiz AI
          </span>
        </Link>

        {/* Nav links */}
        <div style={{ display: 'flex', gap: '0.25rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <NavLink to="/" style={navLinkStyle} end>Dashboard</NavLink>
          <NavLink to="/quiz/1" style={navLinkStyle}>Quiz Arena</NavLink>
          <a href="/#library" style={navLinkStyle({ isActive: false })}>PDF Library</a>
          <NavLink to="/leaderboard" style={navLinkStyle}>Leaderboard</NavLink>
        </div>

        {/* Right side utilities */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <ThemeToggle />

          {loading ? (
            <span
              className="spinner"
              style={{ width: 20, height: 20, borderWidth: 2, display: 'inline-block' }}
            />
          ) : user ? (
            <>
              {/* Cloud sync badge */}
              <span
                className="pill"
                title="Cloud sync"
                style={{ display: 'none', gap: '0.4rem' }}
                className-extra=""
              >
                <Cloud size={13} strokeWidth={2} />
                Supabase Connected
              </span>

              {/* Streak pill */}
              <span
                className="pill"
                title="Daily streak"
                style={{
                  color: 'var(--streak)',
                  borderColor: 'color-mix(in srgb, var(--streak) 35%, transparent)',
                  background: 'color-mix(in srgb, var(--streak) 10%, transparent)',
                }}
              >
                <Flame size={13} strokeWidth={2.2} />
                {user.current_streak} Day Streak
              </span>

              {/* Social bell — friend requests + duels */}
              <div style={{ position: 'relative' }}>
                <button
                  onClick={() => openSocial('requests')}
                  aria-label="Friends and duels"
                  title="Friends & duels"
                  className="btn btn-secondary"
                  style={{
                    padding: '0.45rem 0.55rem',
                    lineHeight: 1,
                    borderRadius: 999,
                    display: 'inline-flex',
                    position: 'relative',
                  }}
                >
                  <Bell size={15} strokeWidth={2} />
                </button>
                {counts.total > 0 && (
                  <span
                    style={{
                      position: 'absolute',
                      top: -5,
                      right: -5,
                      minWidth: 17,
                      height: 17,
                      borderRadius: 10,
                      background: 'var(--danger)',
                      color: '#fff',
                      fontSize: '0.66rem',
                      fontWeight: 700,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      padding: '0 4px',
                      border: '2px solid var(--bg)',
                    }}
                  >
                    {counts.total > 9 ? '9+' : counts.total}
                  </span>
                )}
              </div>

              {/* Avatar + level badge */}
              <div ref={menuRef} style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <button
                  onClick={() => setMenuOpen(o => !o)}
                  aria-label="Account menu"
                  style={{
                    width: 38,
                    height: 38,
                    borderRadius: '50%',
                    background: 'var(--card-raised)',
                    border: '1px solid var(--card-border-strong)',
                    fontSize: '1.05rem',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    transition: 'transform 0.2s ease, box-shadow 0.2s ease',
                  }}
                >
                  {avatarEmoji(user.avatar)}
                </button>
                <span
                  className="pill"
                  style={{
                    display: 'none',
                    fontSize: '0.72rem',
                    padding: '0.22rem 0.65rem',
                    color: 'var(--accent)',
                    borderColor: 'color-mix(in srgb, var(--accent) 35%, transparent)',
                    background: 'var(--accent-soft)',
                  }}
                >
                  {levelLabel(user.gk_skill_tier)}
                </span>

                {menuOpen && (
                  <div
                    className="card"
                    style={{
                      position: 'absolute',
                      right: 0,
                      top: 'calc(100% + 0.6rem)',
                      minWidth: 230,
                      borderRadius: 'var(--radius-md)',
                      boxShadow: 'var(--shadow-raised)',
                      padding: '0.6rem',
                      zIndex: 100,
                    }}
                  >
                    <div
                      style={{
                        padding: '0.5rem 0.6rem 0.7rem',
                        borderBottom: '1px solid var(--card-border)',
                        marginBottom: '0.4rem',
                      }}
                    >
                      <div style={{ fontWeight: 650, fontSize: '0.92rem' }}>
                        {avatarEmoji(user.avatar)} {user.username}
                      </div>
                      <div style={{ color: 'var(--text-secondary)', fontSize: '0.78rem', marginTop: '0.15rem' }}>
                        🎯 {levelLabel(user.gk_skill_tier)}
                      </div>
                    </div>
                    <Link
                      to="/profile"
                      onClick={() => setMenuOpen(false)}
                      className="btn btn-ghost"
                      style={{
                        display: 'flex',
                        width: '100%',
                        textAlign: 'left',
                        color: 'var(--text)',
                        fontSize: '0.88rem',
                        padding: '0.55rem 0.7rem',
                        borderRadius: 'var(--radius-sm)',
                        justifyContent: 'flex-start',
                      }}
                    >
                      <User size={14} strokeWidth={2} /> My Profile
                    </Link>
                    <button
                      onClick={handleLogout}
                      className="btn"
                      style={{
                        width: '100%',
                        textAlign: 'left',
                        background: 'transparent',
                        borderRadius: 'var(--radius-sm)',
                        padding: '0.55rem 0.7rem',
                        color: 'var(--danger)',
                        fontSize: '0.88rem',
                        justifyContent: 'flex-start',
                      }}
                    >
                      <LogOut size={14} strokeWidth={2} /> Log Out
                    </button>
                  </div>
                )}
              </div>
            </>
          ) : (
            <>
              <Link to="/login" className="btn btn-secondary" style={{ padding: '0.45rem 1.1rem', fontSize: '0.88rem' }}>
                Log In
              </Link>
              <Link to="/signup" className="btn btn-primary" style={{ padding: '0.45rem 1.2rem', fontSize: '0.88rem' }}>
                Get Started
              </Link>
            </>
          )}
        </div>
      </nav>
    </header>
  );
}
