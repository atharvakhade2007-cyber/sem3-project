import { useEffect, useState } from 'react';
import LeaderboardPanel from '../components/LeaderboardPanel';
import { fetchFriendLeaderboard } from '../api';
import { useAuth } from '../context/AuthContext';
import { avatarEmoji, TIER_LABELS } from '../constants';

const FRIEND_METRICS = [
  { key: 'all_time', label: '📚 All-Time Correct' },
  { key: 'streak', label: '🔥 Streaks' },
  { key: 'elo', label: '🎯 Skill (Elo)' },
];

const METRIC_DESC = {
  all_time: 'Total correct answers across every daily quiz you and your friends have played',
  streak: 'Current daily streaks in your friend circle',
  elo: 'Skill rating from adaptive PDF tests',
};

const MEDALS = ['🥇', '🥈', '🥉'];
const TIER_COLOR = { easy: 'var(--success-text)', medium: 'var(--warning-text)', hard: 'var(--danger-text)' };

function FriendLeaderboardPanel() {
  const { user } = useAuth();
  const [metric, setMetric] = useState('all_time');
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchFriendLeaderboard(metric)
      .then(d => { if (!cancelled) setData(d); })
      .catch(e => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [metric]);

  const entries = data?.leaderboard || [];

  const valueFor = (e) => {
    if (metric === 'all_time') return `${e.metric_value} ${e.metric_value === 1 ? 'correct' : 'correct'}`;
    if (metric === 'streak') return `🔥 ${e.metric_value}`;
    return `${e.metric_value} Elo`;
  };

  return (
    <div style={{
      background: 'var(--card-bg)', border: '1px solid var(--card-border)',
      borderRadius: 20, padding: '1.5rem', marginTop: '1.5rem',
    }}>
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
        {FRIEND_METRICS.map(m => {
          const active = metric === m.key;
          return (
            <button key={m.key} onClick={() => setMetric(m.key)} style={{
              background: active ? 'var(--accent-gradient)' : 'var(--surface-1)',
              border: active ? 'none' : '1px solid var(--card-border)',
              borderRadius: 10, padding: '0.55rem 1rem',
              color: active ? '#fff' : 'var(--text-secondary)', fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer',
            }}>
              {m.label}
            </button>
          );
        })}
      </div>
      <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
        {METRIC_DESC[metric]} · scoped to your friends
      </p>

      {loading && (
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textAlign: 'center', padding: '1rem' }}>
          Loading friends leaderboard…
        </p>
      )}
      {!loading && error && (
        <p style={{ color: 'var(--danger-text)', fontSize: '0.85rem', textAlign: 'center', padding: '1rem' }}>
          {error}
        </p>
      )}
      {!loading && !error && entries.length === 0 && (
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textAlign: 'center', padding: '1rem' }}>
          {metric === 'all_time'
            ? 'No daily-quiz activity among your friends yet.'
            : 'No rankings to show among your friends yet.'}
        </p>
      )}
      {!loading && !error && entries.length > 0 && (
        <div>
          {entries.map(e => {
            const isMe = e.is_me || e.username === user?.username;
            return (
              <div key={e.rank} style={{
                display: 'flex', alignItems: 'center', gap: '0.75rem',
                padding: '0.55rem 0.75rem', borderRadius: 10, marginBottom: '0.25rem',
                background: isMe ? 'rgba(99,102,241,0.14)' : 'transparent',
                border: isMe ? '1px solid rgba(99,102,241,0.4)' : '1px solid transparent',
              }}>
                <span style={{ width: 30, textAlign: 'center', fontSize: '1.05rem', flexShrink: 0 }}>
                  {e.rank <= 3 ? MEDALS[e.rank - 1]
                    : <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>{e.rank}</span>}
                </span>
                <span style={{ fontSize: '1.1rem' }}>{e.avatar_emoji || avatarEmoji(e.avatar)}</span>
                <span style={{
                  flex: 1, fontWeight: isMe ? 800 : 600, fontSize: '0.9rem',
                  color: isMe ? 'var(--accent-text)' : undefined,
                }}>
                  {e.username} {isMe && <span style={{ fontSize: '0.68rem', background: 'rgba(99,102,241,0.3)', padding: '0.1rem 0.45rem', borderRadius: 8, marginLeft: 4 }}>you</span>}
                </span>
                <span style={{
                  fontSize: '0.7rem', padding: '0.15rem 0.55rem', borderRadius: 20,
                  background: 'color-mix(in srgb, ' + (TIER_COLOR[e.gk_skill_tier] || 'var(--text-secondary)') + ' 16%, transparent)',
                  color: TIER_COLOR[e.gk_skill_tier] || 'var(--text-secondary)', flexShrink: 0,
                }}>
                  {TIER_LABELS[e.gk_skill_tier] || e.gk_skill_tier}
                </span>
                <span style={{
                  fontWeight: 800, fontSize: '0.92rem', minWidth: 92, textAlign: 'right',
                  color: metric === 'elo' ? 'var(--warning-text)' : metric === 'streak' ? 'var(--warning-text)' : 'var(--success-text)',
                }}>
                  {valueFor(e)}
                </span>
              </div>
            );
          })}
          {data?.meta?.my_rank != null && data.meta.total_users > 1 && (
            <p style={{
              textAlign: 'center', marginTop: '0.75rem', fontSize: '0.82rem',
              color: 'var(--accent-text)', fontWeight: 700,
            }}>
              Rank #{data.meta.my_rank} of {data.meta.total_users} in your circle
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export default function LeaderboardPage() {
  const [scope, setScope] = useState('global');

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '2rem 1.5rem' }}>
      <h1 style={{ fontSize: '1.6rem', fontWeight: 800, marginBottom: '0.5rem' }}>
        🏆 Leaderboards
      </h1>
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1rem' }}>
        Today's top scorers, streak legends — or your own friend circle.
      </p>

      {/* Scope toggle */}
      <div style={{
        display: 'inline-flex', gap: '0.25rem', background: 'var(--surface-1)',
        border: '1px solid var(--card-border)', borderRadius: 12, padding: '0.25rem',
      }}>
        {[
          { key: 'global', label: '🌍 Global' },
          { key: 'friends', label: '🤝 Friends' },
        ].map(s => {
          const active = scope === s.key;
          return (
            <button key={s.key} onClick={() => setScope(s.key)} style={{
              background: active ? 'var(--accent-gradient)' : 'transparent',
              border: 'none', borderRadius: 9, padding: '0.55rem 1.4rem',
              color: active ? '#fff' : 'var(--text-secondary)',
              fontSize: '0.88rem', fontWeight: 700, cursor: 'pointer',
            }}>
              {s.label}
            </button>
          );
        })}
      </div>

      {scope === 'global' ? <LeaderboardPanel /> : <FriendLeaderboardPanel />}
    </div>
  );
}
