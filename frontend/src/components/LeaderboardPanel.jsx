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
const TIER_COLOR = { easy: '#34d399', medium: '#fbbf24', hard: '#f87171' };
const MEDALS = ['🥇', '🥈', '🥉'];

const TABS = [
  { key: 'score', label: "🏆 Today's Scores" },
  { key: 'streak', label: '🔥 Streak Legends' },
];

// ─── Rows ─────────────────────────────────────────

function ScoreRow({ entry }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '0.75rem',
      padding: '0.55rem 0.75rem', borderRadius: 10,
      borderBottom: '1px solid rgba(255,255,255,0.05)',
    }}>
      <span style={{ width: 30, textAlign: 'center', fontSize: '1.05rem', flexShrink: 0 }}>
        {entry.rank <= 3
          ? MEDALS[entry.rank - 1]
          : <span style={{ color: '#64748b', fontSize: '0.85rem' }}>{entry.rank}</span>}
      </span>
      <span style={{ flex: 1, fontWeight: entry.rank <= 3 ? 600 : 400, fontSize: '0.9rem' }}>
        {entry.username}
      </span>
      <span style={{ color: '#64748b', fontSize: '0.78rem' }}>{formatTime(entry.time_sec)}</span>
      <span style={{
        fontWeight: 800, fontSize: '0.95rem', minWidth: 52, textAlign: 'right',
        color: entry.score >= 8 ? '#34d399' : entry.score >= 5 ? '#fbbf24' : '#94a3b8',
      }}>
        {entry.score}/10
      </span>
    </div>
  );
}

function StreakRow({ entry }) {
  const tier = entry.gk_skill_tier;
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '0.75rem',
      padding: '0.55rem 0.75rem', borderRadius: 10,
      borderBottom: '1px solid rgba(255,255,255,0.05)',
    }}>
      <span style={{ width: 30, textAlign: 'center', fontSize: '1.05rem', flexShrink: 0 }}>
        {entry.rank <= 3
          ? MEDALS[entry.rank - 1]
          : <span style={{ color: '#64748b', fontSize: '0.85rem' }}>{entry.rank}</span>}
      </span>
      <span style={{ flex: 1, fontWeight: entry.rank <= 3 ? 600 : 400, fontSize: '0.9rem' }}>
        {entry.username}
      </span>
      <span style={{
        fontSize: '0.75rem', padding: '0.15rem 0.6rem', borderRadius: 20,
        background: `${TIER_COLOR[tier] || '#94a3b8'}22`,
        color: TIER_COLOR[tier] || '#94a3b8', border: `1px solid ${TIER_COLOR[tier] || '#94a3b8'}44`,
        flexShrink: 0,
      }}>
        {TIER_LABEL[tier] || tier}
      </span>
      <span style={{
        fontWeight: 800, fontSize: '0.95rem', minWidth: 90, textAlign: 'right',
        color: entry.current_streak >= 7 ? '#fb923c' : '#fbbf24',
      }}>
        🔥 {entry.current_streak} <span style={{ color: '#64748b', fontWeight: 400, fontSize: '0.75rem' }}>best {entry.longest_streak}</span>
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
    ? "No participants yet today — be the first to play! 🚀"
    : "No streaks yet — come back tomorrow to keep yours alive! 🔥";

  return (
    <div style={{
      background: 'rgba(30,41,59,0.7)', border: '1px solid rgba(255,255,255,0.1)',
      borderRadius: 20, padding: '1.5rem', marginTop: '1.5rem',
    }}>
      {/* Tabs */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
        {TABS.map(t => {
          const active = tab === t.key;
          return (
            <button key={t.key} onClick={() => setTab(t.key)} style={{
              background: active ? 'linear-gradient(135deg, #6366f1, #8b5cf6)' : 'rgba(255,255,255,0.05)',
              border: active ? 'none' : '1px solid rgba(255,255,255,0.1)',
              borderRadius: 10, padding: '0.55rem 1.1rem',
              color: active ? '#fff' : '#94a3b8',
              fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer',
              transition: 'all 0.15s',
            }}>
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Body */}
      {loading && (
        <p style={{ color: '#64748b', fontSize: '0.85rem', textAlign: 'center', padding: '1rem' }}>
          Loading leaderboard...
        </p>
      )}
      {!loading && error && (
        <p style={{ color: '#fca5a5', fontSize: '0.85rem', textAlign: 'center', padding: '1rem' }}>
          {error}
        </p>
      )}
      {!loading && !error && entries.length === 0 && (
        <p style={{ color: '#64748b', fontSize: '0.85rem', textAlign: 'center', padding: '1rem' }}>
          {emptyMessage}
        </p>
      )}
      {!loading && !error && entries.length > 0 && (
        <div>
          {tab === 'score' && (
            <>
              <div style={{ fontSize: '0.72rem', color: '#64748b', padding: '0 0.75rem 0.35rem' }}>
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
