import { useState, useEffect, useRef, useCallback } from 'react';
import { fetchDailyQuiz, submitDailyQuiz, checkDailyQuizAnswer } from '../api';
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
const TIER_COLOR = { easy: 'var(--tier-easy)', medium: 'var(--tier-medium)', hard: 'var(--tier-hard)' };
const CATEGORY_LABEL = {
  current_affairs: { text: '📰 Current Affairs', color: 'var(--clay)' },
  gk: { text: '🧠 General Knowledge', color: 'var(--plum)' },
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
  const tierColor = TIER_COLOR[tier] || 'var(--text-secondary)';
  return (
    <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1.4rem' }}>
      <span
        className="pill"
        style={{ color: 'var(--streak)', borderColor: 'color-mix(in srgb, var(--streak) 35%, transparent)', background: 'color-mix(in srgb, var(--streak) 10%, transparent)' }}
      >
        🔥 {current} day streak
      </span>
      <span className="pill">
        🏆 Best: {longest}
      </span>
      <span
        className="pill"
        style={{ color: tierColor, borderColor: `color-mix(in srgb, ${tierColor} 27%, transparent)`, background: `color-mix(in srgb, ${tierColor} 9%, transparent)` }}
      >
        🎯 GK Level: {TIER_LABEL[tier] || tier}
      </span>
    </div>
  );
}

// ─── Countdown timer (presentational) ─────────────

function QuizCountdown({ remaining }) {
  const danger = remaining <= 60;
  return (
    <span
      style={{
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
        fontWeight: 700,
        fontSize: '1.02rem',
        fontVariantNumeric: 'tabular-nums',
        color: danger ? 'var(--danger)' : 'var(--text)',
        background: danger ? 'color-mix(in srgb, var(--danger) 12%, transparent)' : 'var(--input-bg)',
        border: `1px solid ${danger ? 'color-mix(in srgb, var(--danger) 40%, transparent)' : 'var(--card-border)'}`,
        borderRadius: 999,
        padding: '0.32rem 0.85rem',
      }}
    >
      ⏱ {formatCountdown(remaining)}
    </span>
  );
}

// ─── Skeleton Loader ──────────────────────────────

function SkeletonCard() {
  return (
    <div className="card" style={{ padding: '2.25rem' }}>
      <div className="skeleton" style={{ width: 200, height: 24, marginBottom: 16 }} />
      <div className="skeleton" style={{ width: '100%', height: 16, marginBottom: 12 }} />
      <div className="skeleton" style={{ width: '60%', height: 16, marginBottom: 20 }} />
      <div className="skeleton" style={{ width: 180, height: 44, borderRadius: 999 }} />
    </div>
  );
}

// ─── Mini Top-3 (hero) ────────────────────────────

function MiniLeaderboard({ entries }) {
  const medals = ['🥇', '🥈', '🥉'];

  if (!entries || entries.length === 0) {
    return (
      <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textAlign: 'center', padding: '1rem' }}>
        No participants yet. Be the first!
      </div>
    );
  }

  return (
    <div>
      {entries.map((e, i) => (
        <div
          key={i}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
            padding: '0.5rem 0',
            borderBottom: i < entries.length - 1 ? '1px solid var(--card-border)' : 'none',
          }}
        >
          <span style={{ fontSize: '1.05rem', width: 28, textAlign: 'center' }}>
            {i < 3 ? medals[i] : <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>{i + 1}</span>}
          </span>
          <span style={{ flex: 1, fontWeight: i < 3 ? 600 : 400, fontSize: '0.9rem' }}>
            {e.username}
          </span>
          <span
            style={{
              fontWeight: 700,
              fontSize: '0.92rem',
              fontVariantNumeric: 'tabular-nums',
              color: e.score >= 8 ? 'var(--success)' : e.score >= 5 ? 'var(--streak)' : 'var(--text-secondary)',
            }}
          >
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
      <div
        className="card wash-warm"
        style={{ padding: '2.25rem', display: 'grid', gridTemplateColumns: '1fr 280px', gap: '2rem', alignItems: 'center' }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.9rem', flexWrap: 'wrap' }}>
            <span className="pill" style={{ color: 'var(--streak)', borderColor: 'color-mix(in srgb, var(--streak) 35%, transparent)', background: 'color-mix(in srgb, var(--streak) 10%, transparent)' }}>
              Daily challenge
            </span>
            <span className="t-caption" style={{ fontSize: '0.8rem' }}>
              {new Date(quizData.date + 'T00:00:00').toLocaleDateString('en-US', {
                weekday: 'long', month: 'long', day: 'numeric', year: 'numeric'
              })}
            </span>
          </div>

          <h2 className="t-headline">
            🧠 Daily GK &amp; Current Affairs Quiz
          </h2>

          <p className="t-body" style={{ margin: '0.75rem 0 1.4rem', fontSize: '0.92rem' }}>
            {quizData.total_questions} questions — 5 from today's headlines + 5 tuned to your GK level.
            <br />
            <span style={{ color: 'var(--text-muted)' }}>⏱ ~3 min · 📊 Global Leaderboard</span>
          </p>

          <StreakChips
            current={quizData.current_streak}
            longest={quizData.longest_streak}
            tier={quizData.gk_skill_tier}
          />

          <button onClick={onStart} className="btn btn-primary" style={{ padding: '0.85rem 1.9rem', fontSize: '0.98rem' }}>
            ▶ Play Daily Quiz ({quizData.total_questions} Questions)
          </button>
        </div>

        {/* Mini Top-3 */}
        <div
          style={{
            background: 'var(--input-bg)',
            borderRadius: 'var(--radius-md)',
            padding: '1.1rem 1.3rem',
            border: '1px solid var(--card-border)',
          }}
        >
          <h4 className="t-eyebrow" style={{ marginBottom: '0.75rem' }}>
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

function QuizRunner({ questions, checkedAnswers = [], onComplete }) {
  const [currentIdx, setCurrentIdx] = useState(0);
  // { [questionId]: { question_id, selected_index, is_correct, correct_index,
  //                   explanation, ... } } — every entry is a LOCKED answer
  // recorded by the server via /daily-quiz/check/. answered ⇒ reviewed.
  const [answers, setAnswers] = useState(() => {
    const init = {};
    (checkedAnswers || []).forEach(a => {
      if (a && a.question_id != null && a.selected_index != null) {
        init[a.question_id] = a;
      }
    });
    return init;
  });
  // question id whose answer is currently being graded by the server
  const [checkingId, setCheckingId] = useState(null);
  // option the user just tapped, highlighted while the server grades it
  const [pendingIdx, setPendingIdx] = useState(null);
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
      .map(q => (answers[q.id] ? {
        question_id: q.id,
        selected_index: answers[q.id].selected_index,
      } : null))
      .filter(Boolean);

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

  // Grade + lock one answer. The server reveals the outcome in the same
  // request, so reviewing never races with an unlocked answer.
  const checkAnswer = useCallback(async (questionId, selectedIdx) => {
    if (submitting || checkingId) return; // one in-flight check at a time
    setPendingIdx(selectedIdx);
    setCheckingId(questionId);
    setError(null);
    try {
      const res = await checkDailyQuizAnswer(questionId, selectedIdx);
      setAnswers(prev => (prev[questionId]
        ? prev // already locked server-side — keep the original outcome
        : { ...prev, [questionId]: res }));
    } catch (e) {
      setError(e.message);
    } finally {
      setCheckingId(null);
      setPendingIdx(null);
    }
  }, [submitting, checkingId]);

  const handleSelect = useCallback((selectedIdx) => {
    if (submitting || !current) return;
    if (answers[current.id] || checkingId) return; // locked / busy
    checkAnswer(current.id, selectedIdx);
  }, [submitting, current, answers, checkingId, checkAnswer]);

  if (submitting) {
    return (
      <div className="card" style={{ padding: '3rem', textAlign: 'center' }}>
        <div className="spinner" style={{ margin: '0 auto 1rem' }} />
        <p className="t-body">Grading your answers...</p>
      </div>
    );
  }

  if (!current) return null;

  const cat = CATEGORY_LABEL[current.category] || null;
  // Locked review for the visible question (null while unanswered)
  const review = answers[current.id] || null;
  const isChecking = checkingId === current.id;
  const keys = ['A', 'B', 'C', 'D'];

  // Move to the next question after reviewing this one.
  const goNext = () => {
    if (currentIdx < total - 1) setCurrentIdx(i => Math.min(total - 1, i + 1));
  };

  return (
    <div className="card" style={{ padding: '2.25rem' }}>
      {/* Header: progress + timer */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', gap: '1rem', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
          Question {currentIdx + 1} of {total}
          {cat && (
            <span
              style={{
                marginLeft: '0.75rem',
                fontSize: '0.75rem',
                fontWeight: 650,
                color: cat.color,
                background: `color-mix(in srgb, ${cat.color} 9%, transparent)`,
                border: `1px solid color-mix(in srgb, ${cat.color} 24%, transparent)`,
                borderRadius: 999,
                padding: '0.15rem 0.7rem',
              }}
            >
              {cat.text}
            </span>
          )}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Answered {answeredCount}/{total}
          </span>
          <QuizCountdown remaining={remaining} />
        </div>
      </div>

      <div className="progress-track" style={{ marginBottom: '2rem' }}>
        <div className="progress-fill" style={{ width: `${(answeredCount / total) * 100}%` }} />
      </div>

      {/* Question */}
      <h3 style={{ fontSize: '1.2rem', fontWeight: 650, letterSpacing: '-0.02em', marginBottom: '1.6rem', lineHeight: 1.5 }}>
        {current.question_text}
      </h3>

      {/* Options — one answer per question: tapping locks it and reveals the review */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.7rem' }}>
        {current.options.map((opt, idx) => {
          const isCorrectOption = review && idx === review.correct_index;
          const isWrongSelected = review && idx === review.selected_index && !review.is_correct;
          const isChosen = !!review && idx === review.selected_index;
          const isPendingPick = isChecking && pendingIdx === idx;
          const disabled = !!review || isChecking;

          let bg = 'var(--input-bg)';
          let borderColor = 'var(--card-border)';
          if (isPendingPick) {
            bg = 'var(--accent-soft)';
            borderColor = 'var(--accent)';
          } else if (isCorrectOption) {
            bg = 'color-mix(in srgb, var(--success) 12%, transparent)';
            borderColor = 'var(--success)';
          } else if (isWrongSelected) {
            bg = 'color-mix(in srgb, var(--danger) 10%, transparent)';
            borderColor = 'var(--danger)';
          }

          return (
            <button
              key={idx}
              onClick={() => handleSelect(idx)}
              disabled={disabled}
              style={{
                background: bg,
                border: `1px solid ${borderColor}`,
                borderRadius: 'var(--radius-sm)',
                padding: '1rem 1.2rem',
                color: 'var(--text)',
                fontSize: '0.95rem',
                fontFamily: 'inherit',
                cursor: disabled ? 'default' : 'pointer',
                textAlign: 'left',
                transition: 'background 0.2s, border-color 0.2s, transform 0.2s',
                display: 'flex',
                alignItems: 'center',
                gap: '0.8rem',
                opacity: review && !isChosen && !isCorrectOption ? 0.5 : 1,
              }}
              onMouseEnter={e => {
                if (!disabled && !isChosen) {
                  e.currentTarget.style.borderColor = 'var(--accent)';
                  e.currentTarget.style.background = 'var(--accent-soft)';
                }
              }}
              onMouseLeave={e => {
                if (!disabled && !isChosen) {
                  e.currentTarget.style.borderColor = borderColor;
                  e.currentTarget.style.background = bg;
                }
              }}
            >
              <span
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: 9,
                  background: isCorrectOption
                    ? 'var(--success)'
                    : isWrongSelected
                      ? 'var(--danger)'
                      : isPendingPick
                        ? 'var(--accent)'
                        : 'var(--input-bg)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.78rem',
                  fontWeight: 700,
                  flexShrink: 0,
                  color: (isCorrectOption || isWrongSelected) ? '#fff' : (isPendingPick ? 'var(--accent-contrast)' : 'var(--text-secondary)'),
                }}
              >
                {review && idx === review.correct_index ? '✓' : String.fromCharCode(65 + idx)}
              </span>
              {opt}
              {isChosen && (
                <span
                  style={{
                    marginLeft: 'auto',
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    color: review.is_correct ? 'var(--success)' : 'var(--danger)',
                    flexShrink: 0,
                  }}
                >
                  {review.is_correct ? 'Correct' : 'Your answer'}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Per-question review — shown only for the question just answered */}
      {isChecking && !review && (
        <div style={{ marginTop: '1rem', fontSize: '0.85rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span
            className="spinner"
            style={{ width: 16, height: 16, borderWidth: 2, display: 'inline-block' }}
          />
          Locking in your answer…
        </div>
      )}

      {review && (
        <div
          style={{
            marginTop: '1.4rem',
            padding: '1.1rem 1.3rem',
            borderRadius: 'var(--radius-md)',
            background: review.is_correct ? 'color-mix(in srgb, var(--success) 8%, transparent)' : 'color-mix(in srgb, var(--danger) 8%, transparent)',
            border: `1px solid ${review.is_correct ? 'color-mix(in srgb, var(--success) 30%, transparent)' : 'color-mix(in srgb, var(--danger) 30%, transparent)'}`,
          }}
        >
          <div
            style={{
              fontWeight: 700,
              fontSize: '0.95rem',
              color: review.is_correct ? 'var(--success)' : 'var(--danger)',
              marginBottom: '0.25rem',
            }}
          >
            {review.is_correct
              ? '✓ Correct!'
              : `✗ Incorrect — the answer is ${keys[review.correct_index]}: ${current.options[review.correct_index]}`}
          </div>
          {review.explanation && (
            <div style={{ marginTop: '0.4rem', color: 'var(--text-secondary)', fontSize: '0.88rem', lineHeight: 1.55 }}>
              💡 {review.explanation}
            </div>
          )}
          <div style={{ marginTop: '0.6rem', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
            🔒 Answer locked — pick carefully, you can't change it once revealed.
          </div>
          {currentIdx < total - 1 && (
            <button onClick={goNext} className="btn btn-primary" style={{ marginTop: '0.9rem', padding: '0.55rem 1.3rem', fontSize: '0.86rem' }}>
              Next Question →
            </button>
          )}
        </div>
      )}

      {/* Dynamic question navigation grid */}
      <div
        style={{
          marginTop: '1.9rem',
          paddingTop: '1.4rem',
          borderTop: '1px solid var(--card-border)',
        }}
      >
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(40px, 1fr))',
            gap: '0.45rem',
          }}
        >
          {questions.map((q, idx) => {
            const answered = answers[q.id] != null;
            const isCurrent = idx === currentIdx;
            return (
              <button
                key={q.id}
                onClick={() => setCurrentIdx(idx)}
                style={{
                  aspectRatio: '1',
                  borderRadius: 'var(--radius-sm)',
                  background: isCurrent
                    ? 'var(--accent)'
                    : answered
                      ? 'color-mix(in srgb, var(--success) 16%, transparent)'
                      : 'var(--input-bg)',
                  border: isCurrent
                    ? 'none'
                    : answered
                      ? '1px solid color-mix(in srgb, var(--success) 40%, transparent)'
                      : '1px solid var(--card-border)',
                  color: isCurrent ? 'var(--accent-contrast)' : answered ? 'var(--success)' : 'var(--text-muted)',
                  fontWeight: 700,
                  fontSize: '0.9rem',
                  fontFamily: 'inherit',
                  cursor: 'pointer',
                  transition: 'transform 0.15s ease, background 0.2s',
                }}
              >
                {answered ? '✓' : idx + 1}
              </button>
            );
          })}
        </div>

        {/* Prev / Next / Submit */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginTop: '1.4rem', flexWrap: 'wrap' }}>
          <button
            onClick={() => setCurrentIdx(i => Math.max(0, i - 1))}
            disabled={currentIdx === 0}
            className="btn btn-secondary"
            style={{ opacity: currentIdx === 0 ? 0.4 : 1, cursor: currentIdx === 0 ? 'not-allowed' : 'pointer' }}
          >
            ← Previous
          </button>
          {currentIdx < total - 1 && (
            <button
              onClick={() => setCurrentIdx(i => Math.min(total - 1, i + 1))}
              className="btn btn-secondary"
            >
              Next →
            </button>
          )}
          <div style={{ flex: 1 }} />
          <button
            onClick={() => doSubmit(false)}
            disabled={!allAnswered || isChecking}
            className={allAnswered && !isChecking ? 'btn btn-primary' : 'btn btn-secondary'}
            style={allAnswered && !isChecking ? { background: 'var(--success)', boxShadow: '0 6px 18px color-mix(in srgb, var(--success) 30%, transparent)' } : { opacity: 0.5, cursor: 'not-allowed' }}
          >
            {isChecking ? 'Saving…' : `Submit Quiz ${allAnswered ? '' : `(${answeredCount}/${total})`}`}
          </button>
        </div>
      </div>

      {error && (
        <div
          style={{
            marginTop: '1rem',
            padding: '0.75rem 1rem',
            background: 'color-mix(in srgb, var(--danger) 10%, transparent)',
            border: '1px solid color-mix(in srgb, var(--danger) 30%, transparent)',
            borderRadius: 'var(--radius-sm)',
            color: 'var(--danger)',
            fontSize: '0.85rem',
          }}
        >
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

  const scoreColor = score >= 8 ? 'var(--success)' : score >= 5 ? 'var(--streak)' : 'var(--danger)';
  const badge = score >= 9 ? '🏆' : score >= 7 ? '⭐' : score >= 5 ? '👍' : '📚';

  return (
    <div className="card wash-green" style={{ padding: '2.25rem' }}>
      {/* Score header */}
      <div style={{ textAlign: 'center', marginBottom: '1.75rem' }}>
        <div style={{ fontSize: '2.8rem', marginBottom: '0.4rem' }}>{badge}</div>
        <h2 className="t-headline">
          Quiz Complete!
        </h2>

        {/* Streak + level summary */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'center',
            gap: '0.6rem',
            flexWrap: 'wrap',
            margin: '1rem 0 1.4rem',
          }}
        >
          <span
            className="pill"
            style={{ color: 'var(--streak)', borderColor: 'color-mix(in srgb, var(--streak) 35%, transparent)', background: 'color-mix(in srgb, var(--streak) 10%, transparent)' }}
          >
            🔥 Streak: {result.current_streak}
            <span style={{ color: 'var(--text-muted)', fontWeight: 500, fontSize: '0.76rem', marginLeft: '0.3rem' }}>
              best {result.longest_streak}
            </span>
          </span>
          {result.gk_skill_tier && (
            <span
              className="pill"
              style={{ color: 'var(--plum)', borderColor: 'color-mix(in srgb, var(--plum) 40%, transparent)', background: 'color-mix(in srgb, var(--plum) 10%, transparent)' }}
            >
              🎯 Level: {TIER_LABEL[result.gk_skill_tier] || result.gk_skill_tier}
              {tierChanged && <span style={{ marginLeft: '0.3rem' }}>↑</span>}
            </span>
          )}
        </div>

        <div style={{ display: 'flex', justifyContent: 'center', gap: '2.25rem', marginTop: '0.5rem' }}>
          <div>
            <div style={{ fontSize: '2.1rem', fontWeight: 700, letterSpacing: '-0.03em', color: scoreColor }}>
              {score}/{total}
            </div>
            <div className="t-caption" style={{ fontSize: '0.78rem' }}>Score</div>
          </div>
          <div style={{ width: 1, background: 'var(--card-border)' }} />
          <div>
            <div style={{ fontSize: '2.1rem', fontWeight: 700, letterSpacing: '-0.03em' }}>{formatTime(time)}</div>
            <div className="t-caption" style={{ fontSize: '0.78rem' }}>Time</div>
          </div>
          <div style={{ width: 1, background: 'var(--card-border)' }} />
          <div>
            <div style={{ fontSize: '2.1rem', fontWeight: 700, letterSpacing: '-0.03em' }}>#{rank}</div>
            <div className="t-caption" style={{ fontSize: '0.78rem' }}>Rank</div>
          </div>
        </div>
      </div>

      {/* Review toggle */}
      <button
        onClick={() => setShowReview(r => !r)}
        className="btn btn-secondary"
        style={{
          width: '100%',
          padding: '0.85rem 1.25rem',
          justifyContent: 'space-between',
          fontSize: '0.9rem',
          borderRadius: 'var(--radius-sm)',
        }}
      >
        <span>📝 Review Answers &amp; Explanations</span>
        <span style={{ transition: 'transform 0.25s', transform: showReview ? 'rotate(180deg)' : 'none', display: 'inline-block' }}>
          ▾
        </span>
      </button>

      {showReview && (
        <div style={{ marginTop: '1rem' }}>
          {review.map((r, i) => (
            <div
              key={i}
              style={{
                padding: '1rem 1.25rem',
                marginBottom: '0.7rem',
                background: r.is_correct ? 'color-mix(in srgb, var(--success) 7%, transparent)' : 'color-mix(in srgb, var(--danger) 7%, transparent)',
                border: `1px solid ${r.is_correct ? 'color-mix(in srgb, var(--success) 20%, transparent)' : 'color-mix(in srgb, var(--danger) 20%, transparent)'}`,
                borderRadius: 'var(--radius-sm)',
              }}
            >
              <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.4rem' }}>
                <span>{r.is_correct ? '✅' : '❌'}</span>
                <span style={{ fontWeight: 600, fontSize: '0.9rem', lineHeight: 1.5 }}>
                  {r.question_text}
                </span>
              </div>
              {!r.is_correct && r.options && (
                <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>
                  Your answer: <span style={{ color: 'var(--danger)' }}>{r.options[r.selected_index]}</span>
                  {' · '}Correct: <span style={{ color: 'var(--success)' }}>{r.options[r.correct_index]}</span>
                </div>
              )}
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.45 }}>
                💡 {r.explanation}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Countdown to next quiz */}
      <div
        style={{
          marginTop: '1.6rem',
          textAlign: 'center',
          padding: '1rem',
          background: 'var(--input-bg)',
          borderRadius: 'var(--radius-sm)',
          border: '1px solid var(--card-border)',
        }}
      >
        <span className="t-caption" style={{ fontSize: '0.8rem' }}>
          🔒 Next quiz unlocks at midnight IST in{' '}
        </span>
        <span
          style={{
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
            fontWeight: 700,
            fontSize: '1.05rem',
            fontVariantNumeric: 'tabular-nums',
          }}
        >
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
      <div className="card" style={{ padding: '2rem', textAlign: 'center', borderColor: 'color-mix(in srgb, var(--danger) 30%, transparent)' }}>
        <div style={{ fontSize: '1.8rem', marginBottom: '0.5rem' }}>⚠️</div>
        <p style={{ color: 'var(--danger)' }}>{error}</p>
        <button
          onClick={() => window.location.reload()}
          className="btn btn-secondary"
          style={{ marginTop: '1rem' }}
        >
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
          checkedAnswers={quizData.checked_answers || []}
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
