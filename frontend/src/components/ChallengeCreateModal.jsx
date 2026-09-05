import { useEffect, useState } from 'react';
import { useUi } from '../context/UiContext';
import { avatarEmoji, TIER_LABELS } from '../constants';
import {
  createChallenge,
  fetchFriends,
  fetchMyCompletedSessions,
} from '../api';

const TIER_COLOR = { easy: '#34d399', medium: '#fbbf24', hard: '#f87171' };

function fmtTime(sec) {
  if (sec == null) return '—';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

export default function ChallengeCreateModal() {
  const { challengeSpec, closeChallenge, openSocial } = useUi();
  const [sessions, setSessions] = useState([]);
  const [friends, setFriends] = useState([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(null);
  const [created, setCreated] = useState(null);

  const hasFriend = !!challengeSpec?.friend;
  const hasSession = !!challengeSpec?.session;
  const open = hasFriend || hasSession;

  useEffect(() => {
    if (!open) return;
    setCreated(null);
    setNotice(null);
    setBusy(false);
    if (hasFriend) {
      fetchMyCompletedSessions()
        .then(d => setSessions(d.sessions || []))
        .catch(() => setSessions([]));
    } else if (hasSession) {
      fetchFriends()
        .then(d => setFriends(d.friends?.map(f => f.friend) || []))
        .catch(() => setFriends([]));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, challengeSpec]);

  if (!open) return null;

  const sendDuel = async (payload) => {
    setBusy(true);
    setNotice(null);
    try {
      const res = await createChallenge(payload.sessionId, payload.friendId);
      setCreated(res);
    } catch (e) {
      setNotice(e.message || 'Could not create the duel.');
    } finally {
      setBusy(false);
    }
  };

  const friend = challengeSpec.friend;
  const session = challengeSpec.session;

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 210,
      background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem',
    }} onClick={closeChallenge}>
      <div onClick={e => e.stopPropagation()} style={{
        width: 'min(520px, 100%)', maxHeight: '82vh', overflow: 'hidden',
        background: 'var(--card-bg-solid, #111622)', border: '1px solid var(--card-border)',
        borderRadius: 20, boxShadow: '0 30px 80px rgba(0,0,0,0.5)',
        display: 'flex', flexDirection: 'column',
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '1rem 1.25rem', borderBottom: '1px solid var(--card-border)',
        }}>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 800, margin: 0 }}>⚔️ Launch a Duel</h2>
          <button onClick={closeChallenge} style={{
            background: 'none', border: 'none', color: 'var(--text-secondary)',
            fontSize: '1.3rem', cursor: 'pointer', lineHeight: 1, padding: '0.2rem 0.5rem',
          }}>✕</button>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '1rem 1.25rem 1.25rem' }}>
          {created ? (
            <div style={{ textAlign: 'center', padding: '1.5rem 0' }}>
              <div style={{ fontSize: '2.4rem', marginBottom: '0.5rem' }}>🎯</div>
              <h3 style={{ marginBottom: '0.5rem' }}>
                Duel sent to {created.challenged_username}!
              </h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1rem' }}>
                {created.document_filename} · {created.question_count} questions · their score to beat:{' '}
                {created.challenger_score}/{created.question_count}
              </p>
              <div style={{ display: 'flex', gap: '0.6rem', justifyContent: 'center' }}>
                <button
                  onClick={() => { closeChallenge(); openSocial('duels'); }}
                  style={{ padding: '0.6rem 1.2rem', borderRadius: 10, background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', border: 'none', color: '#fff', fontWeight: 700, cursor: 'pointer' }}
                >View Duels</button>
                <button
                  onClick={closeChallenge}
                  style={{ padding: '0.6rem 1.2rem', borderRadius: 10, background: 'none', border: '1px solid var(--card-border)', color: 'var(--text)', fontWeight: 600, cursor: 'pointer' }}
                >Close</button>
              </div>
            </div>
          ) : (
            <>
              {notice && (
                <div style={{
                  padding: '0.55rem 0.8rem', borderRadius: 8, marginBottom: '0.8rem',
                  fontSize: '0.82rem', background: 'rgba(248,113,113,0.12)',
                  border: '1px solid rgba(248,113,113,0.3)', color: '#fca5a5',
                }}>{notice}</div>
              )}

              {hasFriend && (
                <>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>
                    Dueling <strong style={{ color: 'var(--text)' }}>{friend.username}</strong>. Pick one of your
                    completed study sessions as the quiz:
                  </p>
                  {sessions.length === 0 && (
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', textAlign: 'center', padding: '2rem 0' }}>
                      📄 You don't have any completed PDF tests yet — finish an adaptive test first.
                    </p>
                  )}
                  {sessions.map(s => (
                    <button key={s.session_id} disabled={busy}
                      onClick={() => sendDuel({ sessionId: s.session_id, friendId: friend.user_id })}
                      style={{
                        width: '100%', textAlign: 'left', marginTop: '0.5rem',
                        padding: '0.8rem 0.95rem', borderRadius: 12, cursor: 'pointer',
                        background: 'var(--card-bg)', border: '1px solid var(--card-border)',
                        color: 'var(--text)', display: 'flex', alignItems: 'center', gap: '0.75rem',
                      }}>
                      <span style={{ fontSize: '1.3rem' }}>📄</span>
                      <span style={{ flex: 1, minWidth: 0 }}>
                        <span style={{ display: 'block', fontWeight: 700, fontSize: '0.88rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {s.document_filename}
                        </span>
                        <span style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                          {s.correct_count}/{s.questions_answered} correct ({s.accuracy}%) · {fmtTime(s.total_time_sec)}
                        </span>
                      </span>
                      <span style={{
                        background: 'linear-gradient(135deg, #f59e0b, #ef4444)',
                        color: '#fff', borderRadius: 8, padding: '0.4rem 0.8rem',
                        fontSize: '0.78rem', fontWeight: 700, flexShrink: 0,
                      }}>⚔️ Send</span>
                    </button>
                  ))}
                </>
              )}

              {hasSession && (
                <>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>
                    Challenge a friend to beat your score on <strong style={{ color: 'var(--text)' }}>{session.label}</strong>:
                  </p>
                  {friends.length === 0 && (
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', textAlign: 'center', padding: '2rem 0' }}>
                      👥 You need at least one friend to duel — add friends first.
                    </p>
                  )}
                  {friends.map(u => (
                    <button key={u.user_id} disabled={busy}
                      onClick={() => sendDuel({ sessionId: session.sessionId, friendId: u.user_id })}
                      style={{
                        width: '100%', textAlign: 'left', marginTop: '0.5rem',
                        padding: '0.8rem 0.95rem', borderRadius: 12, cursor: 'pointer',
                        background: 'var(--card-bg)', border: '1px solid var(--card-border)',
                        color: 'var(--text)', display: 'flex', alignItems: 'center', gap: '0.75rem',
                      }}>
                      <span style={{
                        width: 38, height: 38, borderRadius: '50%', flexShrink: 0,
                        background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.1rem',
                      }}>{avatarEmoji(u.avatar)}</span>
                      <span style={{ flex: 1, minWidth: 0 }}>
                        <span style={{ display: 'block', fontWeight: 700, fontSize: '0.9rem' }}>{u.username}</span>
                        <span style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                          {TIER_LABELS[u.gk_skill_tier] || 'Intermediate'} · 🔥 {u.current_streak}
                        </span>
                      </span>
                      <span style={{
                        background: 'linear-gradient(135deg, #f59e0b, #ef4444)', color: '#fff',
                        borderRadius: 8, padding: '0.4rem 0.8rem', fontSize: '0.78rem', fontWeight: 700, flexShrink: 0,
                      }}>⚔️ Challenge</span>
                    </button>
                  ))}
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
