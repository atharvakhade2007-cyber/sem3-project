import { useState, useEffect, useRef, useCallback } from 'react';
import { fetchDailyQuiz, submitDailyQuiz } from '../api';
import LeaderboardPanel from './LeaderboardPanel';

// ─── Helpers ──────────────────────────────────────

const QUIZ_LIMIT_SEC = 10 * 60; // 10-minute countdown per quiz

function formatTime(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}m ${s}s`;
}

function pad(n) {
  return String(n).padStart(2, '0');
}

function formatCountdown(sec) {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${pad(m)}:${pad(s)}`;
}

// Reset countdown (can span many hours) reads as hours + minutes (+ seconds).
function formatResetCountdown(sec) {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  if (h > 0) return `${h}h ${pad(m)}m ${pad(s)}s`;
  if (m > 0) return `${m}m ${pad(s)}s`;
  return `${s}s`;
}

const TIER_LABEL = { easy: 'Easy', medium: 'Medium', hard: 'Hard' };
const TIER_COLOR = { easy: '#34d399', medium: '#fbbf24', hard: '#f87171' };
const CATEGORY_LABEL = {
  current_affairs: { text: '📰 Current Affairs', color: '#38bdf8' },
  gk: { text: '🧠 General Knowledge', color: '#a78bfa' },
};

// IST is a fixed UTC+05:30 (no DST), so midnight IST is computable directly.
const IST_OFFSET_MS = 5.5 * 60 * 60 * 1000;

function getTimeUntilMidnightIST(now = Date.now()) {
  // Accept a Date or an epoch-ms number (e.g. from Date.now()).
  const nowMs = now instanceof Date ? now.getTime() : now;
  // Shift the clock to IST, find the next midnight on that clock, then map
  // it back to real time so the diff is measured on the true timeline.
  const nowIST = new Date(nowMs + IST_OFFSET_MS);
  const nextMidnightIST = new Date(Date.UTC(
    nowIST.getUTCFullYear(), nowIST.getUTCMonth(), nowIST.getUTCDate() + 1
  ));
  const realMidnight = nextMidnightIST.getTime() - IST_OFFSET_MS;
  return Math.max(0, Math.floor((realMidnight - nowMs) / 1000));
}

// ─── Streak chips ─────────────────────────────────

function StreakChips({ current, longest, tier }) {
  const tierColor = TIER_COLOR[tier] || '#94a3b8';
  return (
    <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
      <span style={{
        background: 'rgba(251,146,60,0.12)', border: '1px solid rgba(251,146,60,0.35)',
        color: '#fdba74', borderRadius: 20, padding: '0.3rem 0.9rem',
        fontSize: '0.82rem', fontWeight: 700,
      }}>
        🔥 {current} day streak
      </span>
      <span style={{
        background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.12)',
        color: '#94a3b8', borderRadius: 20, padding: '0.3rem 0.9rem',
        fontSize: '0.82rem', fontWeight: 600,
      }}>
        🏆 Best: {longest}
      </span>
      <span style={{
        background: `${tierColor}18`, border: `1px solid ${tierColor}44`,
        color: tierColor, borderRadius: 20, padding: '0.3rem 0.9rem',
        fontSize: '0.82rem', fontWeight: 700,
      }}>
        🎯 GK Level: {TIER_LABEL[tier] || tier}
      </span>
    </div>
  );
}

// ─── Countdown timer (presentational) ─────────────

function QuizCountdown({ remaining }) {
  const danger = remaining <= 60;
  return (
    <span style={{
      fontFamily: 'monospace', fontWeight: 800, fontSize: '1.1rem',
      color: danger ? '#f87171' : '#f8fafc',
      background: danger ? 'rgba(239,68,68,0.15)' : 'rgba(255,255,255,0.05)',
      border: `1px solid ${danger ? 'rgba(239,68,68,0.4)' : 'rgba(255,255,255,0.1)'}`,
      borderRadius: 10, padding: '0.35rem 0.8rem',
    }}>
      ⏱ {formatCountdown(remaining)}
    </span>
  );
}

// ─── Skeleton Loader ──────────────────────────────

function SkeletonCard() {
  const shimmer = {
    background: 'linear-gradient(90deg, rgba(255,255,255,0.04) 25%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.04) 75%)',
    backgroundSize: '200% 100%',
    animation: 'shimmer 1.5s infinite',
    borderRadius: 8,
  };

  return (
    <div style={{
      background: 'rgba(30,41,59,0.7)', border: '1px solid rgba(255,255,255,0.1)',
      borderRadius: 20, padding: '2rem',
    }}>
      <div style={{ ...shimmer, width: 200, height: 24, marginBottom: 16 }} />
      <div style={{ ...shimmer, width: '100%', height: 16, marginBottom: 12 }} />
      <div style={{ ...shimmer, width: '60%', height: 16, marginBottom: 20 }} />
      <div style={{ ...shimmer, width: 180, height: 44, borderRadius: 12 }} />
      <style>{`@keyframes shimmer { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }`}</style>
    </div>
  );
}

// ─── Mini Top-3 (hero) ────────────────────────────

function MiniLeaderboard({ entries }) {
  const medals = ['🥇', '🥈', '🥉'];

  if (!entries || entries.length === 0) {
    return (
      <div style={{ color: '#64748b', fontSize: '0.85rem', textAlign: 'center', padding: '1rem' }}>
        No participants yet. Be the first!
      </div>
    );
  }

  return (
    <div>
      {entries.map((e, i) => (
        <div key={i} style={{
          display: 'flex', alignItems: 'center', gap: '0.75rem',
          padding: '0.5rem 0',
          borderBottom: i < entries.length - 1 ? '1px solid rgba(255,255,255,0.06)' : 'none',
        }}>
          <span style={{ fontSize: '1.1rem', width: 28, textAlign: 'center' }}>
            {i < 3 ? medals[i] : <span style={{ color: '#64748b', fontSize: '0.8rem' }}>{i + 1}</span>}
          </span>
          <span style={{ flex: 1, fontWeight: i < 3 ? 600 : 400, fontSize: '0.9rem' }}>
            {e.username}
          </span>
          <span style={{
            fontWeight: 700, fontSize: '0.95rem',
            color: e.score >= 8 ? '#10b981' : e.score >= 5 ? '#f59e0b' : '#94a3b8',
          }}>
            {e.score}/10
          </span>
        </div>
      ))}
    </div>
  );
}

// ─── State A: Not Started (Dashboard/Hero Card) ───

function HeroCard({ quizData, onStart }) {
  return (
    <div>
      <div style={{
        background: 'linear-gradient(135deg, rgba(99,102,241,0.15), rgba(139,92,246,0.1))',
        border: '1px solid rgba(99,102,241,0.3)',
        borderRadius: 20, padding: '2rem 2.5rem',
        display: 'grid', gridTemplateColumns: '1fr 280px', gap: '2rem', alignItems: 'center',
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <span style={{
              background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              padding: '0.25rem 0.75rem', borderRadius: 20, fontSize: '0.75rem', fontWeight: 700,
            }}>
              DAILY CHALLENGE
            </span>
            <span style={{ color: '#94a3b8', fontSize: '0.8rem' }}>
              {new Date(quizData.date + 'T00:00:00').toLocaleDateString('en-US', {
                weekday: 'long', month: 'long', day: 'numeric', year: 'numeric'
              })}
            </span>
          </div>

          <h2 style={{ fontSize: '1.6rem', fontWeight: 800, marginBottom: '0.5rem' }}>
            🧠 Daily GK & Current Affairs Quiz
          </h2>

          <p style={{ color: '#94a3b8', fontSize: '0.9rem', marginBottom: '1.25rem', lineHeight: 1.5 }}>
            {quizData.total_questions} questions — 5 from today's headlines + 5 tuned to your GK level.
            <br />
            <span style={{ color: '#64748b' }}>⏱ ~3 min &nbsp;|&nbsp; 📊 Global Leaderboard</span>
          </p>

          <StreakChips
            current={quizData.current_streak}
            longest={quizData.longest_streak}
            tier={quizData.gk_skill_tier}
          />

          <button onClick={onStart} style={{
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            color: 'white', border: 'none', borderRadius: 12, padding: '0.85rem 2rem',
            fontSize: '1rem', fontWeight: 700, cursor: 'pointer',
            boxShadow: '0 4px 20px rgba(99,102,241,0.4)',
            transition: 'transform 0.15s, box-shadow 0.15s',
          }}
            onMouseEnter={e => { e.target.style.transform = 'translateY(-2px)'; e.target.style.boxShadow = '0 8px 30px rgba(99,102,241,0.5)'; }}
            onMouseLeave={e => { e.target.style.transform = 'none'; e.target.style.boxShadow = '0 4px 20px rgba(99,102,241,0.4)'; }}
          >
            ▶ Play Daily Quiz ({quizData.total_questions} Questions)
          </button>
        </div>

        {/* Mini Top-3 */}
        <div style={{
          background: 'rgba(15,23,42,0.5)', borderRadius: 14, padding: '1rem 1.25rem',
          border: '1px solid rgba(255,255,255,0.06)',
        }}>
          <h4 style={{ fontSize: '0.75rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.75rem' }}>
            🏆 Today's Top Players
          </h4>
          <MiniLeaderboard entries={quizData.leaderboard_top3} />
        </div>
      </div>

      {/* Tabbed Global Leaderboard */}
      <LeaderboardPanel />
    </div>
  );
}

// ─── State B: Quiz Runner ─────────────────────────

function QuizRunner({ questions, onComplete }) {
  const [currentIdx, setCurrentIdx] = useState(0);
  const [answers, setAnswers] = useState({}); // { [questionId]: selectedIndex }
  const [remaining, setRemaining] = useState(QUIZ_LIMIT_SEC);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const startTimeRef = useRef(Date.now());
  const submittedRef = useRef(false);

  const total = questions.length;
  const current = questions[currentIdx];
  const answeredCount = Object.keys(answers).length;
  const allAnswered = answeredCount === total;

  const doSubmit = useCallback((auto = false) => {
    if (submittedRef.current) return;
    submittedRef.current = true;

    const payload = questions
      .map(q => ({ question_id: q.id, selected_index: answers[q.id] }))
      .filter(a => a.selected_index != null);

    if (payload.length === 0) {
      setError(auto ? 'Time is up — answer at least one question!' : 'Answer at least one question first.');
      submittedRef.current = false;
      return;
    }

    const totalTime = (Date.now() - startTimeRef.current) / 1000;
    setSubmitting(true);
    submitDailyQuiz(payload, totalTime)
      .then(result => onComplete(result))
      .catch(err => {
        setError(err.message);
        setSubmitting(false);
        submittedRef.current = false;
      });
  }, [questions, answers, onComplete]);

  // Keep latest submit fn available to the ticking timer without restarting it.
  const submitRef = useRef(doSubmit);
  useEffect(() => {
    submitRef.current = doSubmit;
  }, [doSubmit]);

  // Countdown → auto-submit at zero.
  useEffect(() => {
    if (submitting) return;
    const iv = setInterval(() => {
      setRemaining(r => {
        if (r <= 1) {
          clearInterval(iv);
          submitRef.current(true);
          return 0;
        }
        return r - 1;
      });
    }, 1000);
    return () => clearInterval(iv);
  }, [submitting]);

  const handleSelect = useCallback((selectedIdx) => {
    if (submitting || !current) return;
    setAnswers(prev => ({ ...prev, [current.id]: selectedIdx }));
    if (currentIdx < total - 1) {
      setTimeout(() => setCurrentIdx(i => Math.min(i + 1, total - 1)), 250);
    }
  }, [submitting, current, currentIdx, total]);

  if (submitting) {
    return (
      <div style={{
        background: 'rgba(30,41,59,0.7)', border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: 20, padding: '3rem', textAlign: 'center',
      }}>
        <div style={{
          width: 48, height: 48, border: '3px solid rgba(99,102,241,0.3)',
          borderTopColor: '#6366f1', borderRadius: '50%',
          animation: 'spin 0.8s linear infinite', margin: '0 auto 1rem',
        }} />
        <p style={{ color: '#94a3b8' }}>Grading your answers...</p>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (!current) return null;

  const cat = CATEGORY_LABEL[current.category] || null;
  const selectedForCurrent = answers[current.id];

  return (
    <div style={{
      background: 'rgba(30,41,59,0.7)', border: '1px solid rgba(255,255,255,0.1)',
      borderRadius: 20, padding: '2rem 2.5rem',
    }}>
      {/* Header: progress + timer */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', gap: '1rem', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>
          Question {currentIdx + 1} of {total}
          {cat && (
            <span style={{
              marginLeft: '0.75rem', fontSize: '0.75rem', fontWeight: 700,
              color: cat.color, background: `${cat.color}18`,
              border: `1px solid ${cat.color}44`, borderRadius: 20,
              padding: '0.15rem 0.7rem',
            }}>
              {cat.text}
            </span>
          )}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
            Answered {answeredCount}/{total}
          </span>
          <QuizCountdown remaining={remaining} />
        </div>
      </div>

      <div style={{
        height: 6, borderRadius: 3, background: 'rgba(255,255,255,0.08)', marginBottom: '2rem', overflow: 'hidden',
      }}>
        <div style={{
          height: '100%', borderRadius: 3, background: 'linear-gradient(90deg, #6366f1, #8b5cf6)',
          width: `${(answeredCount / total) * 100}%`, transition: 'width 0.4s ease',
        }} />
      </div>

      {/* Question */}
      <h3 style={{ fontSize: '1.15rem', fontWeight: 600, marginBottom: '1.5rem', lineHeight: 1.5 }}>
        {current.question_text}
      </h3>

      {/* Options */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {current.options.map((opt, idx) => {
          const isSelected = selectedForCurrent === idx;
          return (
            <button key={idx} onClick={() => handleSelect(idx)} style={{
              background: isSelected ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.04)',
              border: isSelected ? '1px solid rgba(99,102,241,0.7)' : '1px solid rgba(255,255,255,0.12)',
              borderRadius: 12, padding: '1rem 1.25rem',
              color: '#f8fafc', fontSize: '0.95rem',
              cursor: 'pointer', textAlign: 'left',
              transition: 'all 0.15s',
              display: 'flex', alignItems: 'center', gap: '0.75rem',
            }}
              onMouseEnter={e => {
                if (!isSelected) {
                  e.currentTarget.style.background = 'rgba(99,102,241,0.15)';
                  e.currentTarget.style.borderColor = 'rgba(99,102,241,0.4)';
                }
              }}
              onMouseLeave={e => {
                if (!isSelected) {
                  e.currentTarget.style.background = 'rgba(255,255,255,0.04)';
                  e.currentTarget.style.borderColor = 'rgba(255,255,255,0.12)';
                }
              }}
            >
              <span style={{
                width: 28, height: 28, borderRadius: 8,
                background: isSelected ? '#6366f1' : 'rgba(255,255,255,0.08)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '0.8rem', fontWeight: 700, flexShrink: 0,
              }}>
                {String.fromCharCode(65 + idx)}
              </span>
              {opt}
            </button>
          );
        })}
      </div>

      {/* Dynamic question navigation grid */}
      <div style={{
        marginTop: '1.75rem', paddingTop: '1.25rem',
        borderTop: '1px solid rgba(255,255,255,0.07)',
      }}>
        <div style={{
          display: 'grid', gridTemplateColumns: `repeat(auto-fit, minmax(40px, 1fr))`, gap: '0.45rem',
        }}>
          {questions.map((q, idx) => {
            const answered = answers[q.id] != null;
            const isCurrent = idx === currentIdx;
            return (
              <button key={q.id} onClick={() => setCurrentIdx(idx)} style={{
                aspectRatio: '1', borderRadius: 10,
                background: isCurrent
                  ? 'linear-gradient(135deg, #6366f1, #8b5cf6)'
                  : answered
                    ? 'rgba(16,185,129,0.18)'
                    : 'rgba(255,255,255,0.05)',
                border: isCurrent
                  ? 'none'
                  : answered
                    ? '1px solid rgba(16,185,129,0.45)'
                    : '1px solid rgba(255,255,255,0.1)',
                color: isCurrent ? '#fff' : answered ? '#34d399' : '#64748b',
                fontWeight: 700, fontSize: '0.9rem', cursor: 'pointer',
                transition: 'all 0.15s',
              }}>
                {answered ? '✓' : idx + 1}
              </button>
            );
          })}
        </div>

        {/* Prev / Next / Submit */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginTop: '1.25rem' }}>
          <button
            onClick={() => setCurrentIdx(i => Math.max(0, i - 1))}
            disabled={currentIdx === 0}
            style={{
              background: 'rgba(255,255,255,0.05)',
              border: '1px solid rgba(255,255,255,0.12)',
              borderRadius: 10, padding: '0.7rem 1.4rem',
              color: currentIdx === 0 ? '#475569' : '#cbd5e1',
              cursor: currentIdx === 0 ? 'not-allowed' : 'pointer',
              fontSize: '0.9rem', fontWeight: 600,
            }}
          >
            ← Previous
          </button>
          {currentIdx < total - 1 && (
            <button
              onClick={() => setCurrentIdx(i => Math.min(total - 1, i + 1))}
              style={{
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.12)',
                borderRadius: 10, padding: '0.7rem 1.4rem',
                color: '#cbd5e1', cursor: 'pointer', fontSize: '0.9rem', fontWeight: 600,
              }}
            >
              Next →
            </button>
          )}
          <div style={{ flex: 1 }} />
          <button onClick={() => doSubmit(false)} disabled={!allAnswered} style={{
            background: allAnswered ? 'linear-gradient(135deg, #10b981, #059669)' : 'rgba(255,255,255,0.05)',
            border: allAnswered ? 'none' : '1px solid rgba(255,255,255,0.1)',
            borderRadius: 10, padding: '0.7rem 1.6rem',
            color: allAnswered ? '#fff' : '#475569',
            cursor: allAnswered ? 'pointer' : 'not-allowed',
            fontSize: '0.95rem', fontWeight: 800,
            boxShadow: allAnswered ? '0 4px 16px rgba(16,185,129,0.35)' : 'none',
          }}>
            Submit Quiz {allAnswered ? '' : `(${answeredCount}/${total})`}
          </button>
        </div>
      </div>

      {error && (
        <div style={{
          marginTop: '1rem', padding: '0.75rem 1rem',
          background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
          borderRadius: 8, color: '#fca5a5', fontSize: '0.85rem',
        }}>
          {error}
        </div>
      )}
    </div>
  );
}

// ─── State C: Completed ───────────────────────────

function CompletedCard({ quizData, result }) {
  const [showReview, setShowReview] = useState(false);
  // Tick once a second so the "next quiz unlocks" countdown counts down.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const iv = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(iv);
  }, []);

  const score = result.score;
  const total = result.total_questions;
  const time = result.total_time_sec;
  const rank = result.rank;
  const review = result.review || [];

  const tierChanged = quizData.gk_skill_tier && result.gk_skill_tier
    && quizData.gk_skill_tier !== result.gk_skill_tier;

  const scoreColor = score >= 8 ? '#10b981' : score >= 5 ? '#f59e0b' : '#ef4444';
  const badge = score >= 9 ? '🏆' : score >= 7 ? '⭐' : score >= 5 ? '👍' : '📚';

  return (
    <div style={{
      background: 'linear-gradient(135deg, rgba(16,185,129,0.12), rgba(99,102,241,0.08))',
      border: '1px solid rgba(16,185,129,0.25)',
      borderRadius: 20, padding: '2rem 2.5rem',
    }}>
      {/* Score header */}
      <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
        <div style={{ fontSize: '3rem', marginBottom: '0.5rem' }}>{badge}</div>
        <h2 style={{ fontSize: '1.5rem', fontWeight: 800, marginBottom: '0.25rem' }}>
          Quiz Complete!
        </h2>

        {/* Streak + level summary */}
        <div style={{
          display: 'flex', justifyContent: 'center', gap: '1rem', flexWrap: 'wrap',
          marginBottom: '1.25rem',
        }}>
          <span style={{
            background: 'rgba(251,146,60,0.12)', border: '1px solid rgba(251,146,60,0.35)',
            color: '#fdba74', borderRadius: 20, padding: '0.4rem 1.1rem',
            fontSize: '0.9rem', fontWeight: 700,
          }}>
            🔥 Streak: {result.current_streak}
            <span style={{ color: '#64748b', fontWeight: 500, fontSize: '0.78rem', marginLeft: '0.4rem' }}>
              best {result.longest_streak}
            </span>
          </span>
          {result.gk_skill_tier && (
            <span style={{
              background: 'rgba(167,139,250,0.12)', border: '1px solid rgba(167,139,250,0.4)',
              color: '#c4b5fd', borderRadius: 20, padding: '0.4rem 1.1rem',
              fontSize: '0.9rem', fontWeight: 700,
            }}>
              🎯 Level: {TIER_LABEL[result.gk_skill_tier] || result.gk_skill_tier}
              {tierChanged && <span style={{ marginLeft: '0.35rem' }}>↑</span>}
            </span>
          )}
        </div>

        <div style={{ display: 'flex', justifyContent: 'center', gap: '2rem', marginTop: '0.5rem' }}>
          <div>
            <div style={{ fontSize: '2.2rem', fontWeight: 800, color: scoreColor }}>
              {score}/{total}
            </div>
            <div style={{ fontSize: '0.8rem', color: '#64748b' }}>Score</div>
          </div>
          <div style={{ width: 1, background: 'rgba(255,255,255,0.1)' }} />
          <div>
            <div style={{ fontSize: '2.2rem', fontWeight: 800 }}>{formatTime(time)}</div>
            <div style={{ fontSize: '0.8rem', color: '#64748b' }}>Time</div>
          </div>
          <div style={{ width: 1, background: 'rgba(255,255,255,0.1)' }} />
          <div>
            <div style={{ fontSize: '2.2rem', fontWeight: 800 }}>#{rank}</div>
            <div style={{ fontSize: '0.8rem', color: '#64748b' }}>Rank</div>
          </div>
        </div>
      </div>

      {/* Review toggle */}
      <button onClick={() => setShowReview(r => !r)} style={{
        width: '100%', background: 'rgba(255,255,255,0.04)',
        border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12,
        padding: '0.85rem 1.25rem', color: '#f8fafc',
        cursor: 'pointer', fontSize: '0.9rem', fontWeight: 600,
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <span>📝 Review Answers & Explanations</span>
        <span style={{ transition: 'transform 0.2s', transform: showReview ? 'rotate(180deg)' : 'none' }}>
          ▾
        </span>
      </button>

      {showReview && (
        <div style={{ marginTop: '1rem' }}>
          {review.map((r, i) => (
            <div key={i} style={{
              padding: '1rem 1.25rem', marginBottom: '0.75rem',
              background: r.is_correct ? 'rgba(16,185,129,0.08)' : 'rgba(239,68,68,0.08)',
              border: `1px solid ${r.is_correct ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)'}`,
              borderRadius: 12,
            }}>
              <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem' }}>
                <span>{r.is_correct ? '✅' : '❌'}</span>
                <span style={{ fontWeight: 600, fontSize: '0.9rem', lineHeight: 1.5 }}>
                  {r.question_text}
                </span>
              </div>
              {!r.is_correct && r.options && (
                <div style={{ fontSize: '0.82rem', color: '#94a3b8', marginBottom: '0.25rem' }}>
                  Your answer: <span style={{ color: '#fca5a5' }}>{r.options[r.selected_index]}</span>
                  {' · '}Correct: <span style={{ color: '#6ee7b7' }}>{r.options[r.correct_index]}</span>
                </div>
              )}
              <div style={{ fontSize: '0.8rem', color: '#64748b', lineHeight: 1.4 }}>
                💡 {r.explanation}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Countdown to next quiz */}
      <div style={{
        marginTop: '1.5rem', textAlign: 'center',
        padding: '1rem', background: 'rgba(255,255,255,0.03)',
        borderRadius: 10, border: '1px solid rgba(255,255,255,0.06)',
      }}>
        <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
          🔒 Next quiz unlocks at midnight IST in{' '}
        </span>
        <span style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: '1.1rem' }}>
          {formatResetCountdown(getTimeUntilMidnightIST(now))}
        </span>
      </div>
    </div>
  );
}

// ─── Main Component ───────────────────────────────

export default function DailyQuiz() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [quizData, setQuizData] = useState(null);
  const [view, setView] = useState('hero'); // 'hero' | 'quiz' | 'completed'
  const [result, setResult] = useState(null);

  useEffect(() => {
    setLoading(true);
    fetchDailyQuiz()
      .then(data => {
        setQuizData(data);
        if (data.user_completed) {
          setResult({
            score: data.user_score,
            total_time_sec: data.user_time_sec,
            rank: data.user_rank,
            total_questions: data.total_questions,
            review: data.user_review || data.user_answers || [],
            current_streak: data.current_streak,
            longest_streak: data.longest_streak,
            gk_skill_tier: data.gk_skill_tier,
          });
          setView('completed');
        }
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <SkeletonCard />;
  if (error) {
    return (
      <div style={{
        background: 'rgba(30,41,59,0.7)', border: '1px solid rgba(239,68,68,0.3)',
        borderRadius: 20, padding: '2rem', textAlign: 'center',
      }}>
        <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>⚠️</div>
        <p style={{ color: '#fca5a5' }}>{error}</p>
        <button onClick={() => window.location.reload()} style={{
          marginTop: '1rem', background: 'rgba(255,255,255,0.08)',
          border: '1px solid rgba(255,255,255,0.15)', borderRadius: 8,
          padding: '0.5rem 1.5rem', color: '#f8fafc', cursor: 'pointer',
        }}>
          Retry
        </button>
      </div>
    );
  }
  if (!quizData) return null;

  const handleStart = () => setView('quiz');

  const handleComplete = (res) => {
    setResult(res);
    setView('completed');
  };

  return (
    <div>
      {view === 'hero' && (
        <HeroCard quizData={quizData} onStart={handleStart} />
      )}
      {view === 'quiz' && (
        <QuizRunner
          questions={quizData.questions}
          onComplete={handleComplete}
        />
      )}
      {view === 'completed' && result && (
        <>
          <CompletedCard quizData={quizData} result={result} />
          <LeaderboardPanel />
        </>
      )}
    </div>
  );
}
