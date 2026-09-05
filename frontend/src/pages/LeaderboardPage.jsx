import { useEffect, useState } from 'react';
import LeaderboardPanel from '../components/LeaderboardPanel';
import { fetchFriendLeaderboard } from '../api';
import { useAuth } from '../context/AuthContext';
import { avatarEmoji, TIER_LABELS } from '../constants';

const FRIEND_METRICS = [
  { key: 'all_time', label: '📚 All-Time' },
  { key: 'streak', label: '🔥 Streaks' },
  { key: 'elo', label: '🎯 Skill' },
];

const METRIC_DESC = {
  all_time: 'Total correct answers across every daily quiz you and your friends have played',
  streak: 'Current daily streaks in your friend circle',
  elo: 'Skill rating from adaptive PDF tests',
};

const MEDALS = ['🥇', '🥈', '🥉'];
const TIER_COLOR = { easy: 'var(--tier-easy)', medium: 'var(--tier-medium)', hard: 'var(--tier-hard)' };

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
    if (metric === 'all_time') return `${e.metric_value} correct`;
    if (metric === 'streak') return `🔥 ${e.metric_value}`;
    return `${e.metric_value} Elo`;
  };

  return (
    <div
      className="card"
      style={{ padding: '1.75rem', marginTop: '1.75rem' }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem', marginBottom: '0.9rem' }}>
        <div className="segmented">
          {FRIEND_METRICS.map(m => (
            <button
              key={m.key}
              onClick={() => setMetric(m.key)}
              className={metric === m.key ? 'active' : ''}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>
      <p className="t-caption" style={{ marginBottom: '1.1rem', fontSize: '0.8rem' }}>
        {METRIC_DESC[metric]} · scoped to your friends
      </p>

      {loading && (
        <div style={{ display: 'grid', gap: '0.6rem', padding: '0.5rem 0' }}>
          {[0, 1, 2].map(i => <div key={i} className="skeleton" style={{ height: 44 }} />)}
        </div>
      )}
      {!loading && error && (
        <p style={{ color: 'var(--danger)', fontSize: '0.85rem', textAlign: 'center', padding: '1rem' }}>
          {error}
        </p>
      )}
      {!loading && !error && entries.length === 0 && (
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textAlign: 'center', padding: '1.5rem 0' }}>
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
              <div
                key={e.rank}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.75rem',
                  padding: '0.6rem 0.85rem',
                  borderRadius: 'var(--radius-sm)',
                  marginBottom: '0.25rem',
                  background: isMe ? 'var(--accent-soft)' : 'transparent',
                  border: isMe ? '1px solid color-mix(in srgb, var(--accent) 40%, transparent)' : '1px solid transparent',
                }}
              >
                <span style={{ width: 30, textAlign: 'center', fontSize: '0.95rem', flexShrink: 0 }}>
                  {e.rank <= 3 ? MEDALS[e.rank - 1]
                    : <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>{e.rank}</span>}
                </span>
                <span style={{ fontSize: '1.05rem' }}>{e.avatar_emoji || avatarEmoji(e.avatar)}</span>
                <span
                  style={{
                    flex: 1,
                    fontWeight: isMe ? 700 : 600,
                    fontSize: '0.9rem',
                    color: isMe ? 'var(--accent)' : undefined,
                  }}
                >
                  {e.username}{' '}
                  {isMe && (
                    <span
                      style={{
                        fontSize: '0.66rem',
                        background: 'color-mix(in srgb, var(--accent) 20%, transparent)',
                        color: 'var(--accent)',
                        padding: '0.1rem 0.45rem',
                        borderRadius: 6,
                        marginLeft: 4,
                        fontWeight: 700,
                      }}
                    >
                      you
                    </span>
                  )}
                </span>
                <span
                  style={{
                    fontSize: '0.72rem',
                    padding: '0.15rem 0.6rem',
                    borderRadius: 999,
                  background: `color-mix(in srgb, ${TIER_COLOR[e.gk_skill_tier] || 'var(--text-secondary)'} 12%, transparent)`,
                  color: TIER_COLOR[e.gk_skill_tier] || 'var(--text-secondary)',
                    fontWeight: 600,
                    flexShrink: 0,
                  }}
                >
                  {TIER_LABELS[e.gk_skill_tier] || e.gk_skill_tier}
                </span>
                <span
                  style={{
                    fontWeight: 700,
                    fontSize: '0.9rem',
                    minWidth: 92,
                    textAlign: 'right',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {valueFor(e)}
                </span>
              </div>
            );
          })}
          {data?.meta?.my_rank != null && data.meta.total_users > 1 && (
            <p
              style={{
                textAlign: 'center',
                marginTop: '0.9rem',
                fontSize: '0.82rem',
                color: 'var(--accent)',
                fontWeight: 700,
              }}
            >
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
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '3rem 1.5rem' }}>
      <div className="t-eyebrow rise">Rankings</div>
      <h1 className="t-headline rise rise-1" style={{ marginTop: '0.35rem' }}>
        🏆 Leaderboards
      </h1>
      <p className="t-body rise rise-2" style={{ marginTop: '0.6rem', marginBottom: '1.5rem', maxWidth: 560 }}>
        Today's top scorers, streak legends — or your own friend circle.
      </p>

      {/* Scope toggle */}
      <div className="rise rise-2" style={{ marginBottom: '0.5rem' }}>
        <div className="segmented">
          {[
            { key: 'global', label: '🌍 Global' },
            { key: 'friends', label: '🤝 Friends' },
          ].map(s => (
            <button
              key={s.key}
              onClick={() => setScope(s.key)}
              className={scope === s.key ? 'active' : ''}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {scope === 'global' ? <LeaderboardPanel /> : <FriendLeaderboardPanel />}
    </div>
  );
}
