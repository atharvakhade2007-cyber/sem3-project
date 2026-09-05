import { useCallback, useEffect, useRef, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useUi } from '../context/UiContext';
import { avatarEmoji, TIER_LABELS } from '../constants';
import {
  fetchFriends,
  fetchFriendRequests,
  searchUsers,
  sendFriendRequest,
  respondFriendRequest,
  cancelFriendRequest,
  manageFriend,
  fetchChallenges,
  fetchChallengeQuestions,
  submitChallenge,
} from '../api';

// ─── Shared bits ──────────────────────────────────

function Avatar({ user, size = 40 }) {
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%', flexShrink: 0,
      background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: size * 0.55, position: 'relative',
    }}>
      {avatarEmoji(user?.avatar)}
      {user?.online && (
        <span style={{
          position: 'absolute', right: 0, bottom: 0, width: 12, height: 12,
          borderRadius: '50%', background: '#22c55e',
          border: '2px solid var(--card-bg-solid, #111622)',
        }} title="Online" />
      )}
    </div>
  );
}

function Chip({ children, color = '#94a3b8' }) {
  return (
    <span style={{
      padding: '0.15rem 0.6rem', borderRadius: 20, fontSize: '0.72rem',
      color, border: `1px solid ${color}44`, background: `${color}18`, flexShrink: 0,
    }}>
      {children}
    </span>
  );
}

function fmtTime(sec) {
  if (sec == null) return '—';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

const TIER_COLOR = { easy: '#34d399', medium: '#fbbf24', hard: '#f87171' };

function userTier(u) {
  return u?.gk_skill_tier || 'medium';
}

const btn = (bg, fg = '#fff') => ({
  padding: '0.45rem 0.9rem', borderRadius: 8, border: 'none',
  background: bg, color: fg, fontSize: '0.8rem', fontWeight: 700,
  cursor: 'pointer', whiteSpace: 'nowrap',
});

const rowStyle = {
  display: 'flex', alignItems: 'center', gap: '0.75rem',
  padding: '0.6rem 0.25rem', borderBottom: '1px solid var(--card-border)',
};

// ─── Duel player (answering screen) ───────────────

function DuelPlayer({ challenge, onDone }) {
  const [meta, setMeta] = useState(null);
  const [qIndex, setQIndex] = useState(0);
  const [answers, setAnswers] = useState([]);
  const [selected, setSelected] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const qStart = useRef(Date.now());

  useEffect(() => {
    let cancelled = false;
    fetchChallengeQuestions(challenge.id)
      .then(d => { if (!cancelled) { setMeta(d); setLoading(false); qStart.current = Date.now(); } })
      .catch(e => { if (!cancelled) { setError(e.message); setLoading(false); } });
    return () => { cancelled = true; };
  }, [challenge.id]);

  const question = meta?.questions?.[qIndex];
  const isLast = qIndex === (meta?.questions?.length || 0) - 1;
  const keys = ['A', 'B', 'C', 'D'];

  const recordAnswer = async () => {
    if (selected === null) return;
    const taken = Math.max(0, (Date.now() - qStart.current) / 1000);
    const newAnswers = [...answers, {
      question_id: question.id,
      selected_index: selected,
      time_taken_sec: Math.round(taken * 10) / 10,
    }];
    setAnswers(newAnswers);
    setSelected(null);
    if (isLast) {
      setLoading(true);
      try {
        const res = await submitChallenge(challenge.id, newAnswers);
        setResult(res);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    } else {
      setQIndex(i => i + 1);
      qStart.current = Date.now();
    }
  };

  // ── Result screen
  if (result) {
    const won = result.verdict === 'won';
    const drew = result.verdict === 'draw';
    return (
      <div style={{ textAlign: 'center', padding: '1rem 0.5rem' }}>
        <div style={{ fontSize: '2.6rem', marginBottom: '0.5rem' }}>
          {won ? '🏆' : drew ? '🤝' : '😞'}
        </div>
        <h3 style={{ marginBottom: '1rem', fontSize: '1.15rem' }}>{result.verdict_text}</h3>
        <div style={{
          display: 'flex', justifyContent: 'center', gap: '2.5rem',
          marginBottom: '1.25rem',
        }}>
          <div>
            <div style={{ fontSize: '1.4rem', fontWeight: 800 }}>{result.challenged_score}</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>You</div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>{fmtTime(result.challenged_time_seconds)}</div>
          </div>
          <div style={{ fontSize: '1.5rem', color: 'var(--text-secondary)', alignSelf: 'center' }}>vs</div>
          <div>
            <div style={{ fontSize: '1.4rem', fontWeight: 800 }}>{result.challenger_score}</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{challenge.challenger_username}</div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>{fmtTime(result.challenger_time_seconds)}</div>
          </div>
        </div>
        <button onClick={onDone} style={btn('linear-gradient(135deg, #6366f1, #8b5cf6)')}>
          Done
        </button>
      </div>
    );
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
        {meta ? 'Submitting answers…' : 'Loading duel…'}
      </div>
    );
  }
  if (error) {
    return (
      <div style={{ textAlign: 'center', padding: '2rem' }}>
        <p style={{ color: '#f87171', marginBottom: '1rem' }}>{error}</p>
        <button onClick={onDone} style={btn('var(--card-bg)', 'var(--text)')}>Back</button>
      </div>
    );
  }

  return (
    <div>
      <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
        Dueling <strong>{meta.challenger}</strong> on “{meta.document_filename}” · Question {qIndex + 1} of {meta.total_questions}
      </div>
      <div style={{ height: 5, background: 'rgba(255,255,255,0.1)', borderRadius: 3, marginBottom: '1rem' }}>
        <div style={{
          height: '100%', width: `${((qIndex + (selected !== null ? 1 : 0)) / meta.total_questions) * 100}%`,
          background: 'linear-gradient(90deg, #6366f1, #8b5cf6)', borderRadius: 3,
        }} />
      </div>

      <div style={{ fontSize: '1.02rem', lineHeight: 1.5, marginBottom: '1rem', fontWeight: 600 }}>
        {question?.question_text}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
        {question?.options?.map((opt, i) => {
          const isSel = selected === i;
          return (
            <button key={i} onClick={() => setSelected(i)} style={{
              textAlign: 'left', padding: '0.8rem 0.95rem', borderRadius: 10, cursor: 'pointer',
              fontSize: '0.9rem', width: '100%', color: 'var(--text)',
              background: isSel ? 'rgba(99,102,241,0.18)' : 'var(--card-bg)',
              border: `1px solid ${isSel ? '#6366f1' : 'var(--card-border)'}`,
              display: 'flex', gap: '0.7rem', alignItems: 'center',
            }}>
              <span style={{
                width: 26, height: 26, borderRadius: '50%', flexShrink: 0,
                background: isSel ? '#6366f1' : 'rgba(255,255,255,0.08)',
                color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '0.75rem', fontWeight: 700,
              }}>{keys[i]}</span>
              {opt}
            </button>
          );
        })}
      </div>
      {selected !== null && (
        <button onClick={recordAnswer} style={{
          ...btn('linear-gradient(135deg, #6366f1, #8b5cf6)'),
          width: '100%', padding: '0.8rem', marginTop: '1rem', fontSize: '0.9rem',
        }}>
          {isLast ? '🏁 Finish Duel' : 'Next →'}
        </button>
      )}
    </div>
  );
}

// ─── Duels tab ────────────────────────────────────

function DuelCard({ duel, onPlay, onRefresh }) {
  const { user } = useAuth();
  const incoming = duel.role === 'incoming';
  const opponent = incoming ? duel.challenger_username : duel.challenged_username;
  const opponentAvatar = incoming ? duel.challenger?.avatar : duel.challenged?.avatar;
  const canPlay = incoming && duel.status === 'pending' && !duel.is_expired;
  const expired = duel.status === 'pending' && duel.is_expired;

  let statusChip = null;
  if (expired) statusChip = <Chip color="#f87171">⏰ Expired</Chip>;
  else if (duel.status === 'pending') statusChip = incoming ? <Chip color="#fbbf24">Waiting for you</Chip> : <Chip color="#94a3b8">Awaiting reply…</Chip>;
  else if (duel.status === 'completed') {
    const mine = user?.username === duel.winner_username;
    const drew = !duel.winner_username;
    statusChip = <Chip color={drew ? '#94a3b8' : mine ? '#34d399' : '#f87171'}>
      {drew ? '🤝 Draw' : mine ? '🏆 You won' : `🏆 ${duel.winner_username} won`}
    </Chip>;
  }

  return (
    <div style={rowStyle}>
      <Avatar user={{ avatar: opponentAvatar }} size={36} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 700, fontSize: '0.88rem' }}>
          {incoming ? `${opponent} challenged you` : `You challenged ${opponent}`}
        </div>
        <div style={{ fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
          {duel.document_filename} · {duel.question_count} questions
          {duel.status === 'completed' && (
            <span> · {Math.max(duel.challenger_score ?? 0, duel.challenged_score ?? 0)}/{duel.question_count}</span>
          )}
        </div>
      </div>
      {statusChip}
      {canPlay && (
        <button onClick={() => onPlay(duel)} style={btn('linear-gradient(135deg, #6366f1, #8b5cf6)')}>
          ⚔️ Play
        </button>
      )}
    </div>
  );
}

// ─── Main modal ───────────────────────────────────

const TABS = [
  { key: 'friends', label: '👥 Friends' },
  { key: 'requests', label: '📨 Requests' },
  { key: 'find', label: '🔎 Find Users' },
  { key: 'duels', label: '⚔️ Duels' },
];

export default function SocialHub() {
  const { socialOpen, socialTab, setSocialTab, closeSocial, openChallengeWithFriend } = useUi();
  const { user: me } = useAuth();
  const [friends, setFriends] = useState([]);
  const [requests, setRequests] = useState({ incoming: [], outgoing: [] });
  const [duels, setDuels] = useState({ incoming: [], outgoing: [] });
  const [results, setResults] = useState([]);
  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [busy, setBusy] = useState(false);
  const [activeDuel, setActiveDuel] = useState(null); // duel being played
  const [notice, setNotice] = useState(null);
  const searchTimer = useRef(null);

  const loadAll = useCallback(async () => {
    if (!socialOpen || !me) return;
    try {
      const [f, r, d] = await Promise.all([
        fetchFriends(), fetchFriendRequests(), fetchChallenges(),
      ]);
      setFriends(f.friends || []);
      setRequests(r);
      setDuels({ incoming: d.incoming || [], outgoing: d.outgoing || [] });
      setResults([
        ...(d.incoming || []).filter(x => x.status === 'completed'),
        ...(d.outgoing || []).filter(x => x.status === 'completed'),
      ]);
    } catch { /* ignore */ }
  }, [socialOpen, socialTab, me]);

  useEffect(() => { loadAll(); }, [loadAll]);

  // Debounced search
  useEffect(() => {
    if (socialTab !== 'find' || !me) return;
    if (!query.trim()) { setResults([]); setSearching(false); return; }
    setSearching(true);
    clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(async () => {
      try {
        const d = await searchUsers(query.trim());
        setResults(d.results || []);
      } catch {
        setResults([]);
      } finally {
        setSearching(false);
      }
    }, 300);
    return () => clearTimeout(searchTimer.current);
  }, [query, socialTab, me]);

  const act = async (fn, successMsg) => {
    setBusy(true);
    setNotice(null);
    try {
      await fn();
      if (successMsg) setNotice(successMsg);
      await loadAll();
    } catch (e) {
      setNotice(e.message || 'Something went wrong.');
    } finally {
      setBusy(false);
    }
  };

  const addFriend = (u) => act(
    () => sendFriendRequest(u.user_id),
    `Friend request sent to ${u.username} ✓`
  );

  const respond = (rowId, action, msg) => act(
    () => respondFriendRequest(rowId, action), msg
  );

  const afterDuel = () => { setActiveDuel(null); loadAll(); setSocialTab('duels'); };

  if (!socialOpen || !me) return null;

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 200,
      background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: '1rem',
    }} onClick={closeSocial}>
      <div onClick={e => e.stopPropagation()} style={{
        width: 'min(560px, 100%)', maxHeight: '82vh', overflow: 'hidden',
        background: 'var(--card-bg-solid, #111622)', border: '1px solid var(--card-border)',
        borderRadius: 20, boxShadow: '0 30px 80px rgba(0,0,0,0.5)',
        display: 'flex', flexDirection: 'column',
      }}>
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '1rem 1.25rem', borderBottom: '1px solid var(--card-border)',
        }}>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 800, margin: 0 }}>
            {activeDuel ? '⚔️ Duel' : '🤝 Friends & Duels'}
          </h2>
          <button onClick={closeSocial} style={{
            background: 'none', border: 'none', color: 'var(--text-secondary)',
            fontSize: '1.3rem', cursor: 'pointer', lineHeight: 1, padding: '0.2rem 0.5rem',
          }}>✕</button>
        </div>

        {/* Active duel player replaces the whole body */}
        {activeDuel ? (
          <div style={{ padding: '1.25rem', overflowY: 'auto' }}>
            <DuelPlayer challenge={activeDuel} onDone={afterDuel} />
          </div>
        ) : (
          <>
            {/* Tabs */}
            <div style={{ display: 'flex', gap: '0.35rem', padding: '0.75rem 1.25rem 0', overflowX: 'auto' }}>
              {TABS.map(t => (
                <button key={t.key} onClick={() => setSocialTab(t.key)} style={{
                  background: socialTab === t.key ? 'linear-gradient(135deg, #6366f1, #8b5cf6)' : 'transparent',
                  border: 'none', borderRadius: '10px 10px 0 0', padding: '0.55rem 0.95rem',
                  fontSize: '0.82rem', fontWeight: 700, cursor: 'pointer',
                  color: socialTab === t.key ? '#fff' : 'var(--text-secondary)',
                  borderBottom: socialTab === t.key ? 'none' : '2px solid transparent',
                  whiteSpace: 'nowrap',
                }}>
                  {t.label}
                  {t.key === 'requests' && requests.incoming.length > 0 && (
                    <span style={{
                      marginLeft: 5, background: '#ef4444', color: '#fff', borderRadius: 10,
                      padding: '0.05rem 0.4rem', fontSize: '0.68rem',
                    }}>{requests.incoming.length}</span>
                  )}
                  {t.key === 'duels' && duels.incoming.filter(d => d.status === 'pending' && !d.is_expired).length > 0 && (
                    <span style={{
                      marginLeft: 5, background: '#f59e0b', color: '#fff', borderRadius: 10,
                      padding: '0.05rem 0.4rem', fontSize: '0.68rem',
                    }}>{duels.incoming.filter(d => d.status === 'pending' && !d.is_expired).length}</span>
                  )}
                </button>
              ))}
            </div>

            {/* Notice */}
            {notice && (
              <div style={{
                margin: '0.6rem 1.25rem 0', padding: '0.5rem 0.75rem', borderRadius: 8,
                fontSize: '0.8rem', background: 'rgba(99,102,241,0.15)',
                border: '1px solid rgba(99,102,241,0.3)', color: '#a5b4fc',
              }}>
                {notice}
              </div>
            )}

            {/* Body */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '0.75rem 1.25rem 1.25rem' }}>

              {socialTab === 'friends' && (
                <div>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                    {friends.length === 0
                      ? 'No friends yet — use Find Users to send your first request.'
                      : `${friends.length} friend${friends.length === 1 ? '' : 's'}`}
                  </p>
                  {friends.map(f => {
                    const u = f.friend;
                    return (
                      <div key={f.id} style={rowStyle}>
                        <Avatar user={u} />
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontWeight: 700, fontSize: '0.88rem' }}>
                            {avatarEmoji(u.avatar)} {u.username}
                          </div>
                          <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap', marginTop: '0.2rem' }}>
                            <Chip color={TIER_COLOR[userTier(u)]}>{TIER_LABELS[userTier(u)] || 'Intermediate'}</Chip>
                            <Chip color="#fdba74">🔥 {u.current_streak}</Chip>
                          </div>
                        </div>
                        <button
                          disabled={busy}
                          onClick={() => openChallengeWithFriend(u)}
                          title={`Challenge ${u.username} to a duel`}
                          style={btn('linear-gradient(135deg, #f59e0b, #ef4444)')}
                        >⚔️ Duel</button>
                        <button
                          disabled={busy}
                          onClick={() => act(
                            () => manageFriend(u.user_id, 'remove'),
                            `${u.username} removed from friends.`
                          )}
                          style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '0.9rem' }}
                          title="Remove friend"
                        >🗑️</button>
                      </div>
                    );
                  })}
                </div>
              )}

              {socialTab === 'requests' && (
                <div>
                  {requests.incoming.length === 0 && requests.outgoing.length === 0 && (
                    <p style={{ textAlign: 'center', color: 'var(--text-secondary)', padding: '2rem 0', fontSize: '0.85rem' }}>
                      📭 No pending requests.
                    </p>
                  )}
                  {requests.incoming.map(r => (
                    <div key={r.id} style={rowStyle}>
                      <Avatar user={r.friend} />
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 700, fontSize: '0.88rem' }}>
                          {avatarEmoji(r.friend.avatar)} {r.friend.username}
                        </div>
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                          wants to be your friend
                        </div>
                      </div>
                      <button disabled={busy} onClick={() => respond(r.id, 'accept', `You and ${r.friend.username} are friends! 🎉`)}
                        style={btn('linear-gradient(135deg, #10b981, #22c55e)')}>Accept</button>
                      <button disabled={busy} onClick={() => respond(r.id, 'decline')}
                        style={{ background: 'none', border: '1px solid var(--card-border)', borderRadius: 8, padding: '0.45rem 0.9rem', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', cursor: 'pointer' }}>Decline</button>
                    </div>
                  ))}
                  {requests.outgoing.length > 0 && (
                    <div style={{ marginTop: '0.5rem' }}>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', margin: '0.5rem 0 0.25rem' }}>
                        Outgoing
                      </div>
                      {requests.outgoing.map(r => (
                        <div key={r.id} style={rowStyle}>
                          <Avatar user={r.friend} />
                          <div style={{ flex: 1, fontWeight: 600, fontSize: '0.88rem' }}>
                            {avatarEmoji(r.friend.avatar)} {r.friend.username}
                          </div>
                          <Chip color="#94a3b8">Pending</Chip>
                          <button disabled={busy} onClick={() => act(() => cancelFriendRequest(r.id), 'Request cancelled.')}
                            style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: '0.8rem', textDecoration: 'underline' }}>
                            Cancel
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {socialTab === 'find' && (
                <div>
                  <input
                    value={query}
                    onChange={e => setQuery(e.target.value)}
                    placeholder="Search by username or email…"
                    autoFocus
                    style={{
                      width: '100%', boxSizing: 'border-box', padding: '0.7rem 0.9rem',
                      borderRadius: 10, border: '1px solid var(--card-border)',
                      background: 'var(--card-bg)', color: 'var(--text)',
                      fontSize: '0.9rem', outline: 'none', marginBottom: '0.75rem',
                    }}
                  />
                  {searching && <p style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', textAlign: 'center', padding: '1rem' }}>Searching…</p>}
                  {!searching && query.trim() && results.length === 0 && (
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.82rem', textAlign: 'center', padding: '1.5rem 0' }}>
                      No users found.
                    </p>
                  )}
                  {!searching && results.map(u => (
                    <div key={u.user_id} style={rowStyle}>
                      <Avatar user={u} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontWeight: 700, fontSize: '0.88rem' }}>
                          {avatarEmoji(u.avatar)} {u.username}
                        </div>
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                          {u.username === me.username ? '(you)' : `${TIER_LABELS[userTier(u)] || 'Intermediate'} · 🔥 ${u.current_streak}`}
                        </div>
                      </div>
                      <button disabled={busy} onClick={() => addFriend(u)}
                        style={btn('linear-gradient(135deg, #6366f1, #8b5cf6)')}>
                        + Add Friend
                      </button>
                    </div>
                  ))}
                  {!query.trim() && (
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.82rem', textAlign: 'center', padding: '2rem 0' }}>
                      🔎 Start typing to find users.
                    </p>
                  )}
                </div>
              )}

              {socialTab === 'duels' && (
                <div>
                  {(() => {
                    const playable = duels.incoming.filter(d => d.status === 'pending' && !d.is_expired);
                    const pendingOut = duels.outgoing.filter(d => d.status === 'pending');
                    const past = [
                      ...duels.incoming.filter(d => d.status === 'pending' && d.is_expired),
                      ...duels.outgoing.filter(d => d.status === 'pending' && d.is_expired),
                      ...duels.incoming.filter(d => d.status === 'completed'),
                      ...duels.outgoing.filter(d => d.status === 'completed'),
                    ];
                    if (playable.length === 0 && pendingOut.length === 0 && past.length === 0) {
                      return (
                        <div style={{ textAlign: 'center', padding: '1.5rem 0' }}>
                          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1rem' }}>
                            No duels yet. Challenge a friend from the Friends tab!
                          </p>
                          <button onClick={() => setSocialTab('friends')} style={btn('linear-gradient(135deg, #6366f1, #8b5cf6)')}>
                            👥 Pick a friend
                          </button>
                        </div>
                      );
                    }
                    return (
                      <>
                        {playable.length > 0 && (
                          <div style={{ marginBottom: '0.75rem' }}>
                            <div style={{ fontSize: '0.72rem', color: '#fbbf24', marginBottom: '0.25rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                              ⏳ Waiting on you
                            </div>
                            {playable.map(d => <DuelCard key={d.id} duel={d} onPlay={setActiveDuel} />)}
                          </div>
                        )}
                        {pendingOut.length > 0 && (
                          <div style={{ marginBottom: '0.75rem' }}>
                            <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginBottom: '0.25rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                              Sent
                            </div>
                            {pendingOut.map(d => <DuelCard key={d.id} duel={d} />)}
                          </div>
                        )}
                        {past.length > 0 && (
                          <div>
                            <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginBottom: '0.25rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                              History
                            </div>
                            {past.map(d => <DuelCard key={d.id} duel={d} />)}
                          </div>
                        )}
                      </>
                    );
                  })()}
                </div>
              )}

            </div>
          </>
        )}
      </div>
    </div>
  );
}
