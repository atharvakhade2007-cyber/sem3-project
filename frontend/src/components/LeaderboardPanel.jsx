import { useState, useEffect } from 'react';
import { fetchDailyLeaderboard } from '../api';

// ─── Helpers ──────────────────────────────────────

function formatTime(sec) {
  if (sec == null) return '—';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}m ${s}s`;
}

const TIER_LABEL = { easy: 'Easy', medium: 'Medium', hard: 'Hard' };
const TIER_COLOR = { easy: 'var(--tier-easy)', medium: 'var(--tier-medium)', hard: 'var(--tier-hard)' };
const MEDALS = ['🥇', '🥈', '🥉'];

const TABS = [
  { key: 'score', label: "🏆 Today's Scores" },
  { key: 'streak', label: '🔥 Streak Legends' },
];

// ─── Rows ─────────────────────────────────────────

function ScoreRow({ entry }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '0.75rem',
        padding: '0.6rem 0.85rem',
        borderRadius: 'var(--radius-sm)',
        borderBottom: '1px solid var(--card-border)',
      }}
    >
      <span style={{ width: 30, textAlign: 'center', fontSize: '1rem', flexShrink: 0 }}>
        {entry.rank <= 3
          ? MEDALS[entry.rank - 1]
          : <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>{entry.rank}</span>}
      </span>
      <span style={{ flex: 1, fontWeight: entry.rank <= 3 ? 600 : 400, fontSize: '0.9rem' }}>
        {entry.username}
      </span>
      <span style={{ color: 'var(--text-muted)', fontSize: '0.78rem', fontVariantNumeric: 'tabular-nums' }}>
        {formatTime(entry.time_sec)}
      </span>
      <span
        style={{
          fontWeight: 700,
          fontSize: '0.92rem',
          minWidth: 52,
          textAlign: 'right',
          fontVariantNumeric: 'tabular-nums',
          color: entry.score >= 8 ? 'var(--success)' : entry.score >= 5 ? 'var(--streak)' : 'var(--text-secondary)',
        }}
      >
        {entry.score}/10
      </span>
    </div>
  );
}

function StreakRow({ entry }) {
  const tier = entry.gk_skill_tier;
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '0.75rem',
        padding: '0.6rem 0.85rem',
        borderRadius: 'var(--radius-sm)',
        borderBottom: '1px solid var(--card-border)',
      }}
    >
      <span style={{ width: 30, textAlign: 'center', fontSize: '1rem', flexShrink: 0 }}>
        {entry.rank <= 3
          ? MEDALS[entry.rank - 1]
          : <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>{entry.rank}</span>}
      </span>
      <span style={{ flex: 1, fontWeight: entry.rank <= 3 ? 600 : 400, fontSize: '0.9rem' }}>
        {entry.username}
      </span>
      <span
        style={{
          fontSize: '0.74rem',
          padding: '0.15rem 0.6rem',
          borderRadius: 999,
        background: `color-mix(in srgb, ${TIER_COLOR[tier] || 'var(--text-secondary)'} 9%, transparent)`,
        color: TIER_COLOR[tier] || 'var(--text-secondary)',
        border: `1px solid color-mix(in srgb, ${TIER_COLOR[tier] || 'var(--text-secondary)'} 24%, transparent)`,
          fontWeight: 600,
          flexShrink: 0,
        }}
      >
        {TIER_LABEL[tier] || tier}
      </span>
      <span
        style={{
          fontWeight: 700,
          fontSize: '0.92rem',
          minWidth: 90,
          textAlign: 'right',
          fontVariantNumeric: 'tabular-nums',
          color: 'var(--streak)',
        }}
      >
        🔥 {entry.current_streak}{' '}
        <span style={{ color: 'var(--text-muted)', fontWeight: 400, fontSize: '0.75rem' }}>
          best {entry.longest_streak}
        </span>
      </span>
    </div>
  );
}

// ─── Main Panel ───────────────────────────────────

export default function LeaderboardPanel() {
  const [tab, setTab] = useState('score');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchDailyLeaderboard(tab)
      .then(d => { if (!cancelled) setData(d); })
      .catch(e => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [tab]);

  const entries = data?.leaderboard || [];
  const emptyMessage = tab === 'score'
    ? 'No participants yet today — be the first to play! 🚀'
    : 'No streaks yet — come back tomorrow to keep yours alive! 🔥';

  return (
    <div className="card" style={{ padding: '1.75rem', marginTop: '14px' }}>
      {/* Tabs */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
        <h3 className="t-title">Leaderboard</h3>
        <div className="segmented">
          {TABS.map(t => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={tab === t.key ? 'active' : ''}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Body */}
      {loading && (
        <div style={{ display: 'grid', gap: '0.6rem', padding: '0.5rem 0' }}>
          {[0, 1, 2, 3].map(i => <div key={i} className="skeleton" style={{ height: 42 }} />)}
        </div>
      )}
      {!loading && error && (
        <p style={{ color: 'var(--danger)', fontSize: '0.85rem', textAlign: 'center', padding: '1rem' }}>
          {error}
        </p>
      )}
      {!loading && !error && entries.length === 0 && (
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textAlign: 'center', padding: '1.5rem 0' }}>
          {emptyMessage}
        </p>
      )}
      {!loading && !error && entries.length > 0 && (
        <div>
          {tab === 'score' && (
            <>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', padding: '0 0.85rem 0.4rem' }}>
                {data?.quiz_date} · Ranked by score, then fastest time
              </div>
              {entries.map(e => <ScoreRow key={e.rank} entry={e} />)}
            </>
          )}
          {tab === 'streak' && entries.map(e => <StreakRow key={e.rank} entry={e} />)}
        </div>
      )}
    </div>
  );
}
