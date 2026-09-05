import { useEffect, useState } from 'react';
import { useUi } from '../context/UiContext';
import { avatarEmoji, TIER_LABELS } from '../constants';
import {
  createChallenge,
  fetchFriends,
  fetchMyCompletedSessions,
} from '../api';

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
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 210,
        background: 'rgba(0,0,0,0.45)',
        backdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1rem',
      }}
      onClick={closeChallenge}
    >
      <div
        onClick={e => e.stopPropagation()}
        className="card rise"
        style={{
          width: 'min(520px, 100%)',
          maxHeight: '82vh',
          overflow: 'hidden',
          borderRadius: 'var(--radius-xl)',
          boxShadow: 'var(--shadow-raised)',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '1.1rem 1.4rem',
            borderBottom: '1px solid var(--card-border)',
          }}
        >
          <h2 className="t-title" style={{ margin: 0, fontSize: '1.08rem' }}>⚔️ Launch a Duel</h2>
          <button
            onClick={closeChallenge}
            style={{
              background: 'var(--input-bg)',
              border: 'none',
              color: 'var(--text-secondary)',
              fontSize: '0.9rem',
              cursor: 'pointer',
              lineHeight: 1,
              padding: '0.4rem 0.6rem',
              borderRadius: '50%',
            }}
          >
            ✕
          </button>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '1.1rem 1.4rem 1.4rem' }}>
          {created ? (
            <div style={{ textAlign: 'center', padding: '1.5rem 0' }}>
              <div style={{ fontSize: '2.4rem', marginBottom: '0.5rem' }}>🎯</div>
              <h3 className="t-title" style={{ marginBottom: '0.5rem', fontSize: '1.1rem' }}>
                Duel sent to {created.challenged_username}!
              </h3>
              <p className="t-caption" style={{ marginBottom: '1.1rem' }}>
                {created.document_filename} · {created.question_count} questions · their score to beat:{' '}
                {created.challenger_score}/{created.question_count}
              </p>
              <div style={{ display: 'flex', gap: '0.6rem', justifyContent: 'center' }}>
                <button
                  onClick={() => { closeChallenge(); openSocial('duels'); }}
                  className="btn btn-primary"
                >
                  View Duels
                </button>
                <button onClick={closeChallenge} className="btn btn-secondary">
                  Close
                </button>
              </div>
            </div>
          ) : (
            <>
              {notice && (
                <div
                  style={{
                    padding: '0.55rem 0.85rem',
                    borderRadius: 'var(--radius-sm)',
                    marginBottom: '0.9rem',
                    fontSize: '0.82rem',
                    background: 'rgba(255,69,58,0.1)',
                    border: '1px solid rgba(255,69,58,0.3)',
                    color: 'var(--danger)',
                  }}
                >
                  {notice}
                </div>
              )}

              {hasFriend && (
                <>
                  <p className="t-caption" style={{ marginBottom: '0.3rem', fontSize: '0.85rem' }}>
                    Dueling <strong style={{ color: 'var(--text)' }}>{friend.username}</strong>. Pick one of your
                    completed study sessions as the quiz:
                  </p>
                  {sessions.length === 0 && (
                    <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textAlign: 'center', padding: '2rem 0' }}>
                      📄 You don't have any completed PDF tests yet — finish an adaptive test first.
                    </p>
                  )}
                  {sessions.map(s => (
                    <button
                      key={s.session_id}
                      disabled={busy}
                      onClick={() => sendDuel({ sessionId: s.session_id, friendId: friend.user_id })}
                      className="btn btn-secondary card-hover"
                      style={{
                        width: '100%',
                        textAlign: 'left',
                        marginTop: '0.5rem',
                        padding: '0.85rem 1rem',
                        borderRadius: 'var(--radius-md)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.8rem',
                        justifyContent: 'flex-start',
                      }}
                    >
                      <span className="icon-tile" style={{ width: 40, height: 40, fontSize: '1.1rem' }}>📄</span>
                      <span style={{ flex: 1, minWidth: 0 }}>
                        <span style={{ display: 'block', fontWeight: 650, fontSize: '0.88rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {s.document_filename}
                        </span>
                        <span className="t-caption" style={{ display: 'block', fontSize: '0.75rem' }}>
                          {s.correct_count}/{s.questions_answered} correct ({s.accuracy}%) · {fmtTime(s.total_time_sec)}
                        </span>
                      </span>
                      <span
                        style={{
                          background: 'var(--accent)',
                          color: 'var(--accent-contrast)',
                          borderRadius: 999,
                          padding: '0.4rem 0.85rem',
                          fontSize: '0.78rem',
                          fontWeight: 700,
                          flexShrink: 0,
                        }}
                      >
                        ⚔️ Send
                      </span>
                    </button>
                  ))}
                </>
              )}

              {hasSession && (
                <>
                  <p className="t-caption" style={{ marginBottom: '0.3rem', fontSize: '0.85rem' }}>
                    Challenge a friend to beat your score on <strong style={{ color: 'var(--text)' }}>{session.label}</strong>:
                  </p>
                  {friends.length === 0 && (
                    <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textAlign: 'center', padding: '2rem 0' }}>
                      👥 You need at least one friend to duel — add friends first.
                    </p>
                  )}
                  {friends.map(u => (
                    <button
                      key={u.user_id}
                      disabled={busy}
                      onClick={() => sendDuel({ sessionId: session.sessionId, friendId: u.user_id })}
                      className="btn btn-secondary card-hover"
                      style={{
                        width: '100%',
                        textAlign: 'left',
                        marginTop: '0.5rem',
                        padding: '0.85rem 1rem',
                        borderRadius: 'var(--radius-md)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.8rem',
                        justifyContent: 'flex-start',
                      }}
                    >
                      <span
                        className="icon-tile"
                        style={{ width: 40, height: 40, borderRadius: '50%', fontSize: '1.05rem' }}
                      >
                        {avatarEmoji(u.avatar)}
                      </span>
                      <span style={{ flex: 1, minWidth: 0 }}>
                        <span style={{ display: 'block', fontWeight: 650, fontSize: '0.9rem' }}>{u.username}</span>
                        <span className="t-caption" style={{ display: 'block', fontSize: '0.75rem' }}>
                          {TIER_LABELS[u.gk_skill_tier] || 'Intermediate'} · 🔥 {u.current_streak}
                        </span>
                      </span>
                      <span
                        style={{
                          background: 'var(--accent)',
                          color: 'var(--accent-contrast)',
                          borderRadius: 999,
                          padding: '0.4rem 0.85rem',
                          fontSize: '0.78rem',
                          fontWeight: 700,
                          flexShrink: 0,
                        }}
                      >
                        ⚔️ Challenge
                      </span>
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
