import { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { updateProfile, changePassword, fetchAnalytics } from '../api';
import { AVATARS, eloLevelName } from '../constants';
import StudentAnalyticsDashboard from './StudentAnalyticsDashboard';

const TABS = [
  { key: 'overview', label: '📊 Overview' },
  { key: 'analytics', label: '📈 Analytics' },
  { key: 'edit', label: '✏️ Edit Details' },
  { key: 'security', label: '🔒 Security' },
];

const inputStyle = {
  width: '100%',
  padding: '0.75rem 1rem',
  borderRadius: 10,
  border: '1px solid var(--input-border)',
  background: 'var(--input-bg)',
  color: 'var(--text)',
  fontSize: '0.95rem',
  outline: 'none',
};

const labelStyle = {
  display: 'block',
  fontSize: '0.82rem',
  fontWeight: 600,
  color: 'var(--text-secondary)',
  marginBottom: '0.35rem',
};

function Alert({ type, children }) {
  const isError = type === 'error';
  return (
    <div style={{
      background: isError ? 'rgba(239,68,68,0.1)' : 'rgba(16,185,129,0.1)',
      border: `1px solid ${isError ? 'rgba(239,68,68,0.35)' : 'rgba(16,185,129,0.35)'}`,
      color: isError ? '#fca5a5' : '#34d399',
      borderRadius: 10,
      padding: '0.7rem 1rem',
      fontSize: '0.85rem',
      marginBottom: '1rem',
    }}>
      {children}
    </div>
  );
}

function StatCard({ icon, label, value }) {
  return (
    <div style={{
      background: 'var(--card-bg)',
      border: '1px solid var(--card-border)',
      borderRadius: 14,
      padding: '1.1rem 1.25rem',
      textAlign: 'center',
    }}>
      <div style={{ fontSize: '1.5rem', marginBottom: '0.35rem' }}>{icon}</div>
      <div style={{ fontSize: '1.5rem', fontWeight: 800, lineHeight: 1.1 }}>{value}</div>
      <div style={{ color: 'var(--text-secondary)', fontSize: '0.78rem', marginTop: '0.25rem' }}>
        {label}
      </div>
    </div>
  );
}

export default function Profile() {
  const { user, refreshUser } = useAuth();
  const [tab, setTab] = useState('overview');
  const [alert, setAlert] = useState(null); // {type, text}
  const [analytics, setAnalytics] = useState(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [busy, setBusy] = useState(false);

  const [edit, setEdit] = useState({
    username: '',
    email: '',
    bio: '',
    avatar: 'owl',
  });
  const [pwd, setPwd] = useState({
    old_password: '',
    new_password: '',
    confirm_password: '',
  });

  useEffect(() => {
    if (user) {
      setEdit({
        username: user.username || '',
        email: user.email || '',
        bio: user.bio || '',
        avatar: user.avatar || 'owl',
      });
    }
  }, [user]);

  useEffect(() => {
    if (tab === 'analytics' && !analytics) {
      loadAnalytics();
    }
  }, [tab]);

  // Keep the profile header in sync with the ML-predicted level: re-fetch the
  // profile on mount so persona_tier (single source of truth shared with the
  // Analytics tab) is never stale from a cached login state.
  useEffect(() => {
    refreshUser().catch(() => {});
  }, []);

  if (!user) return null;

  const saveDetails = async e => {
    e.preventDefault();
    setBusy(true);
    setAlert(null);
    try {
      await updateProfile({
        username: edit.username.trim(),
        email: edit.email.trim(),
        bio: edit.bio.trim(),
        avatar: edit.avatar,
      });
      await refreshUser();
      setAlert({ type: 'success', text: 'Profile updated successfully.' });
    } catch (err) {
      setAlert({ type: 'error', text: err.message });
    } finally {
      setBusy(false);
    }
  };

  const loadAnalytics = useCallback(async () => {
    setAnalyticsLoading(true);
    setAlert(null);
    try {
      const data = await fetchAnalytics();
      setAnalytics(data);
    } catch (err) {
      console.error('Analytics load error:', err);
      setAlert({ type: 'error', text: err.message || 'Failed to load analytics.' });
    } finally {
      setAnalyticsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (tab === 'analytics' && !analytics) {
      loadAnalytics();
    }
  }, [tab]);

  const savePassword = async e => {
    e.preventDefault();
    setBusy(true);
    setAlert(null);
    try {
      if (pwd.new_password !== pwd.confirm_password) {
        setAlert({ type: 'error', text: 'New passwords do not match.' });
        return;
      }
      await changePassword(pwd.old_password, pwd.new_password, pwd.confirm_password);
      setPwd({ old_password: '', new_password: '', confirm_password: '' });
      setAlert({ type: 'success', text: 'Password changed successfully.' });
    } catch (err) {
      setAlert({ type: 'error', text: err.message });
    } finally {
      setBusy(false);
    }
  };

  const memberSince = user.created_at
    ? new Date(user.created_at).toLocaleDateString('en-US', {
        month: 'long', year: 'numeric',
      })
    : '—';

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '2rem 1.5rem' }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '1rem',
        marginBottom: '1.5rem', flexWrap: 'wrap',
      }}>
        <div style={{
          width: 64, height: 64, borderRadius: '50%',
          background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '1.9rem',
          border: '2px solid var(--card-border)',
        }}>
          {user.avatar_emoji || '🦉'}
        </div>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 800 }}>{user.username}</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            {user.email}
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div style={{
        display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', flexWrap: 'wrap',
      }}>
        {TABS.map(t => {
          const active = tab === t.key;
          return (
            <button key={t.key} onClick={() => { setTab(t.key); setAlert(null); if (t.key === 'analytics' && !analytics) loadAnalytics(); }} style={{
              background: active ? 'linear-gradient(135deg, #6366f1, #8b5cf6)' : 'var(--card-bg)',
              border: active ? 'none' : '1px solid var(--card-border)',
              borderRadius: 10, padding: '0.55rem 1.1rem',
              color: active ? '#fff' : 'var(--text-secondary)',
              fontSize: '0.88rem', fontWeight: 600, cursor: 'pointer',
            }}>
              {t.label}
            </button>
          );
        })}
      </div>

      {alert && <Alert type={alert.type}>{alert.text}</Alert>}

      {/* ── Analytics ── */}
      {tab === 'analytics' && (
        <StudentAnalyticsDashboard
          analytics={analytics}
          loading={analyticsLoading}
          onRefresh={loadAnalytics}
        />
      )}

      {/* ── Overview ── */}
      {tab === 'overview' && (
        <div>
          {user.bio && (
            <div style={{
              background: 'var(--card-bg)', border: '1px solid var(--card-border)',
              borderRadius: 14, padding: '1.25rem 1.5rem', marginBottom: '1rem',
            }}>
              <div style={{ color: 'var(--text-secondary)', fontSize: '0.78rem', fontWeight: 700, marginBottom: '0.3rem' }}>
                BIO
              </div>
              <p style={{ fontSize: '0.95rem', lineHeight: 1.6 }}>{user.bio}</p>
            </div>
          )}

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
            gap: '1rem',
          }}>
            <StatCard icon="🔥" label="Current Streak" value={user.current_streak ?? 0} />
            <StatCard icon="🏆" label="Longest Streak" value={user.longest_streak ?? 0} />
            <StatCard icon="🎯" label="Level" value={user.persona_tier || 'Intermediate'} />
            <StatCard icon="📈" label="Elo Rating" value={Math.round(user.elo_rating ?? 0)} />
            <StatCard icon="📝" label="Quizzes Completed" value={user.total_quizzes_completed ?? 0} />
            <StatCard icon="❓" label="Questions Answered" value={user.total_questions_answered ?? 0} />
          </div>

          <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginTop: '1.5rem' }}>
            Member since {memberSince}
          </p>
        </div>
      )}

      {/* ── Edit Details ── */}
      {tab === 'edit' && (
        <form onSubmit={saveDetails} style={{
          background: 'var(--card-bg)', border: '1px solid var(--card-border)',
          borderRadius: 16, padding: '1.5rem',
        }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
            <div>
              <label style={labelStyle}>Username</label>
              <input
                value={edit.username}
                onChange={e => setEdit(p => ({ ...p, username: e.target.value }))}
                style={inputStyle}
              />
            </div>
            <div>
              <label style={labelStyle}>Email</label>
              <input
                type="email"
                value={edit.email}
                onChange={e => setEdit(p => ({ ...p, email: e.target.value }))}
                style={inputStyle}
              />
            </div>
          </div>

          <div style={{ marginBottom: '1.25rem' }}>
            <label style={labelStyle}>Bio</label>
            <textarea
              value={edit.bio}
              maxLength={300}
              rows={3}
              onChange={e => setEdit(p => ({ ...p, bio: e.target.value }))}
              placeholder="Tell others a bit about yourself…"
              style={{ ...inputStyle, resize: 'vertical', fontFamily: 'inherit' }}
            />
            <div style={{ textAlign: 'right', fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
              {edit.bio.length}/300
            </div>
          </div>

          <div style={{ marginBottom: '1.5rem' }}>
            <label style={labelStyle}>Avatar</label>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(64px, 1fr))',
              gap: '0.6rem',
            }}>
              {AVATARS.map(a => {
                const selected = edit.avatar === a.key;
                return (
                  <button
                    key={a.key}
                    type="button"
                    title={a.label}
                    onClick={() => setEdit(p => ({ ...p, avatar: a.key }))}
                    style={{
                      aspectRatio: '1',
                      borderRadius: 12,
                      fontSize: '1.5rem',
                      cursor: 'pointer',
                      background: selected ? 'rgba(99,102,241,0.2)' : 'var(--input-bg)',
                      border: selected
                        ? '2px solid #6366f1'
                        : '1px solid var(--input-border)',
                      transition: 'all 0.15s',
                    }}
                  >
                    {a.emoji}
                  </button>
                );
              })}
            </div>
          </div>

          <button type="submit" disabled={busy} style={{
            background: busy ? 'var(--card-border)' : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            color: busy ? 'var(--text-muted)' : '#fff',
            border: 'none', borderRadius: 10, padding: '0.75rem 2rem',
            fontSize: '0.9rem', fontWeight: 700, cursor: 'pointer',
          }}>
            {busy ? 'Saving…' : 'Save Changes'}
          </button>
        </form>
      )}

      {/* ── Security ── */}
      {tab === 'security' && (
        <form onSubmit={savePassword} style={{
          background: 'var(--card-bg)', border: '1px solid var(--card-border)',
          borderRadius: 16, padding: '1.5rem', maxWidth: 440,
        }}>
          <div style={{ marginBottom: '1rem' }}>
            <label style={labelStyle}>Current Password</label>
            <input
              type="password"
              required
              value={pwd.old_password}
              onChange={e => setPwd(p => ({ ...p, old_password: e.target.value }))}
              style={inputStyle}
              autoComplete="current-password"
            />
          </div>
          <div style={{ marginBottom: '1rem' }}>
            <label style={labelStyle}>New Password</label>
            <input
              type="password"
              required
              value={pwd.new_password}
              onChange={e => setPwd(p => ({ ...p, new_password: e.target.value }))}
              placeholder="8+ chars, a number and a symbol"
              style={inputStyle}
              autoComplete="new-password"
            />
          </div>
          <div style={{ marginBottom: '1.5rem' }}>
            <label style={labelStyle}>Confirm New Password</label>
            <input
              type="password"
              required
              value={pwd.confirm_password}
              onChange={e => setPwd(p => ({ ...p, confirm_password: e.target.value }))}
              style={inputStyle}
              autoComplete="new-password"
            />
          </div>

          <button type="submit" disabled={busy} style={{
            background: busy ? 'var(--card-border)' : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            color: busy ? 'var(--text-muted)' : '#fff',
            border: 'none', borderRadius: 10, padding: '0.75rem 2rem',
            fontSize: '0.9rem', fontWeight: 700, cursor: 'pointer',
          }}>
            {busy ? 'Updating…' : 'Change Password'}
          </button>
        </form>
      )}
    </div>
  );
}