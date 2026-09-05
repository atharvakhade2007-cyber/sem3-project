import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { updateProfile, changePassword } from '../api';
import { AVATARS, TIER_LABELS } from '../constants';

const TABS = [
  { key: 'overview', label: '📊 Overview' },
  { key: 'edit', label: '✏️ Edit Details' },
  { key: 'security', label: '🔒 Security' },
];

function Alert({ type, children }) {
  const isError = type === 'error';
  return (
    <div
      style={{
        background: isError ? 'color-mix(in srgb, var(--danger) 10%, transparent)' : 'color-mix(in srgb, var(--success) 10%, transparent)',
        border: `1px solid ${isError ? 'color-mix(in srgb, var(--danger) 30%, transparent)' : 'color-mix(in srgb, var(--success) 30%, transparent)'}`,
        color: isError ? 'var(--danger)' : 'var(--success)',
        borderRadius: 'var(--radius-sm)',
        padding: '0.7rem 1rem',
        fontSize: '0.85rem',
        marginBottom: '1rem',
      }}
    >
      {children}
    </div>
  );
}

function StatCard({ icon, label, value }) {
  return (
    <div className="card card-hover" style={{ padding: '1.25rem 1.35rem', textAlign: 'center' }}>
      <div style={{ fontSize: '1.4rem', marginBottom: '0.4rem' }}>{icon}</div>
      <div style={{ fontSize: '1.55rem', fontWeight: 700, letterSpacing: '-0.03em', lineHeight: 1.1, fontVariantNumeric: 'tabular-nums' }}>
        {value}
      </div>
      <div className="t-caption" style={{ marginTop: '0.3rem', fontSize: '0.76rem' }}>
        {label}
      </div>
    </div>
  );
}

export default function Profile() {
  const { user, refreshUser } = useAuth();
  const [tab, setTab] = useState('overview');
  const [alert, setAlert] = useState(null); // {type, text}
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
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '3rem 1.5rem' }}>
      {/* Header */}
      <div
        className="rise"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '1.1rem',
          marginBottom: '1.75rem',
          flexWrap: 'wrap',
        }}
      >
        <div
          className="icon-tile"
          style={{ width: 64, height: 64, borderRadius: '50%', fontSize: '1.7rem' }}
        >
          {user.avatar_emoji || '🦉'}
        </div>
        <div>
          <h1 className="t-headline" style={{ fontSize: '1.5rem' }}>{user.username}</h1>
          <p className="t-caption">
            {user.email} · 🎯 {TIER_LABELS[user.gk_skill_tier] || user.gk_skill_tier || 'Intermediate'}
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="rise rise-1" style={{ marginBottom: '1.75rem' }}>
        <div className="segmented">
          {TABS.map(t => (
            <button
              key={t.key}
              onClick={() => { setTab(t.key); setAlert(null); }}
              className={tab === t.key ? 'active' : ''}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {alert && <Alert type={alert.type}>{alert.text}</Alert>}

      {/* ── Overview ── */}
      {tab === 'overview' && (
        <div>
          {user.bio && (
            <div className="card" style={{ padding: '1.4rem 1.6rem', marginBottom: '14px' }}>
              <div className="t-eyebrow" style={{ marginBottom: '0.4rem' }}>
                Bio
              </div>
              <p style={{ fontSize: '0.95rem', lineHeight: 1.6 }}>{user.bio}</p>
            </div>
          )}

          <div className="bento">
            <div className="span-2"><StatCard icon="🔥" label="Current Streak" value={user.current_streak ?? 0} /></div>
            <div className="span-2"><StatCard icon="🏆" label="Longest Streak" value={user.longest_streak ?? 0} /></div>
            <div className="span-2"><StatCard icon="🎯" label="Skill Level" value={TIER_LABELS[user.gk_skill_tier] || user.gk_skill_tier || '—'} /></div>
            <div className="span-2"><StatCard icon="📈" label="Elo Rating" value={Math.round(user.elo_rating ?? 1200)} /></div>
            <div className="span-2"><StatCard icon="📝" label="Quizzes Completed" value={user.total_quizzes_completed ?? 0} /></div>
            <div className="span-2"><StatCard icon="❓" label="Questions Answered" value={user.total_questions_answered ?? 0} /></div>
          </div>

          <p className="t-caption" style={{ color: 'var(--text-muted)', fontSize: '0.78rem', marginTop: '1.5rem' }}>
            Member since {memberSince}
          </p>
        </div>
      )}

      {/* ── Edit Details ── */}
      {tab === 'edit' && (
        <form onSubmit={saveDetails} className="card" style={{ padding: '1.75rem' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
            <div>
              <label className="label">Username</label>
              <input
                value={edit.username}
                onChange={e => setEdit(p => ({ ...p, username: e.target.value }))}
                className="input"
              />
            </div>
            <div>
              <label className="label">Email</label>
              <input
                type="email"
                value={edit.email}
                onChange={e => setEdit(p => ({ ...p, email: e.target.value }))}
                className="input"
              />
            </div>
          </div>

          <div style={{ marginBottom: '1.4rem' }}>
            <label className="label">Bio</label>
            <textarea
              value={edit.bio}
              maxLength={300}
              rows={3}
              onChange={e => setEdit(p => ({ ...p, bio: e.target.value }))}
              placeholder="Tell others a bit about yourself…"
              className="textarea"
              style={{ resize: 'vertical' }}
            />
            <div style={{ textAlign: 'right', fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
              {edit.bio.length}/300
            </div>
          </div>

          <div style={{ marginBottom: '1.6rem' }}>
            <label className="label">Avatar</label>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(64px, 1fr))',
                gap: '0.6rem',
              }}
            >
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
                      borderRadius: 'var(--radius-sm)',
                      fontSize: '1.5rem',
                      cursor: 'pointer',
                      background: selected ? 'var(--accent-soft)' : 'var(--input-bg)',
                      border: selected
                        ? '2px solid var(--accent)'
                        : '1px solid var(--input-border)',
                      transition: 'transform 0.2s ease, border-color 0.2s ease',
                      transform: selected ? 'scale(1.05)' : 'none',
                    }}
                  >
                    {a.emoji}
                  </button>
                );
              })}
            </div>
          </div>

          <button type="submit" disabled={busy} className="btn btn-primary">
            {busy ? 'Saving…' : 'Save Changes'}
          </button>
        </form>
      )}

      {/* ── Security ── */}
      {tab === 'security' && (
        <form onSubmit={savePassword} className="card" style={{ padding: '1.75rem', maxWidth: 460 }}>
          <div style={{ marginBottom: '1rem' }}>
            <label className="label">Current Password</label>
            <input
              type="password"
              required
              value={pwd.old_password}
              onChange={e => setPwd(p => ({ ...p, old_password: e.target.value }))}
              className="input"
              autoComplete="current-password"
            />
          </div>
          <div style={{ marginBottom: '1rem' }}>
            <label className="label">New Password</label>
            <input
              type="password"
              required
              value={pwd.new_password}
              onChange={e => setPwd(p => ({ ...p, new_password: e.target.value }))}
              placeholder="8+ chars, a number and a symbol"
              className="input"
              autoComplete="new-password"
            />
          </div>
          <div style={{ marginBottom: '1.5rem' }}>
            <label className="label">Confirm New Password</label>
            <input
              type="password"
              required
              value={pwd.confirm_password}
              onChange={e => setPwd(p => ({ ...p, confirm_password: e.target.value }))}
              className="input"
              autoComplete="new-password"
            />
          </div>

          <button type="submit" disabled={busy} className="btn btn-primary">
            {busy ? 'Updating…' : 'Change Password'}
          </button>
        </form>
      )}
    </div>
  );
}
