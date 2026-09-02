import { useState, useEffect, useRef, useCallback } from 'react';
import { fetchDailyQuiz, submitDailyQuiz, fetchDailyLeaderboard } from '../api';

// ─── Helpers ──────────────────────────────────────

function formatTime(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}m ${s}s`;
}

function pad(n) {
  return String(n).padStart(2, '0');
}

function getTimeUntilMidnightUTC() {
  const now = new Date();
  const tomorrow = new Date(Date.UTC(
    now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1, 0, 0, 0
  ));
  return Math.max(0, Math.floor((tomorrow - now) / 1000));
}

function CountdownTimer({ seconds }) {
  const [remaining, setRemaining] = useState(seconds);

  useEffect(() => {
    if (remaining <= 0) return;
    const iv = setInterval(() => setRemaining(r => Math.max(0, r - 1)), 1000);
    return () => clearInterval(iv);
  }, [remaining]);

  const h = Math.floor(remaining / 3600);
  const m = Math.floor((remaining % 3600) / 60);
  const s = remaining % 60;

  return (
    <span style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: '1.1rem' }}>
      {pad(h)}:{pad(m)}:{pad(s)}
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

// ─── Leaderboard Card ─────────────────────────────

function LeaderboardCard({ entries, compact = false }) {
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
          padding: compact ? '0.4rem 0' : '0.5rem 0',
          borderBottom: i < entries.length - 1 ? '1px solid rgba(255,255,255,0.06)' : 'none',
        }}>
          <span style={{ fontSize: compact ? '0.9rem' : '1.1rem', width: 28, textAlign: 'center' }}>
            {i < 3 ? medals[i] : <span style={{ color: '#64748b', fontSize: '0.8rem' }}>{i + 1}</span>}
          </span>
          <span style={{
            flex: 1, fontWeight: i < 3 ? 600 : 400,
            fontSize: compact ? '0.82rem' : '0.9rem',
          }}>
            {e.username}
          </span>
          <span style={{
            fontWeight: 700, fontSize: compact ? '0.85rem' : '0.95rem',
            color: e.score >= 8 ? '#10b981' : e.score >= 5 ? '#f59e0b' : '#94a3b8',
          }}>
            {e.score}/10
          </span>
          {!compact && e.time_sec != null && (
            <span style={{ color: '#64748b', fontSize: '0.75rem' }}>{formatTime(e.time_sec)}</span>
          )}
        </div>
      ))}
    </div>
  );
}

// ─── State A: Not Started (Hero Card) ─────────────

function HeroCard({ quizData, onStart }) {
  return (
    <div style={{
      background: 'linear-gradient(135deg, rgba(99,102,241,0.15), rgba(139,92,246,0.1))',
      border: '1px solid rgba(99,102,241,0.3)',
      borderRadius: 20, padding: '2rem 2.5rem',
      display: 'grid', gridTemplateColumns: '1fr 280px', gap: '2rem', alignItems: 'center',
    }}>
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
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
          Test your knowledge with {quizData.total_questions} handpicked questions from today's headlines.
          <br />
          <span style={{ color: '#64748b' }}>⏱ ~3 min &nbsp;|&nbsp; 📊 Global Leaderboard</span>
        </p>

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

      {/* Mini Leaderboard */}
      <div style={{
        background: 'rgba(15,23,42,0.5)', borderRadius: 14, padding: '1rem 1.25rem',
        border: '1px solid rgba(255,255,255,0.06)',
      }}>
        <h4 style={{ fontSize: '0.75rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.75rem' }}>
          🏆 Today's Top Players
        </h4>
        <LeaderboardCard entries={quizData.leaderboard_top3} compact />
      </div>
    </div>
  );
}

// ─── State B: Quiz Runner ─────────────────────────

function QuizRunner({ questions, onComplete }) {
  const [currentIdx, setCurrentIdx] = useState(0);
  const [answers, setAnswers] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const startTimeRef = useRef(Date.now());
  const current = questions[currentIdx];

  const handleSelect = useCallback((selectedIdx) => {
    const newAnswers = [...answers, {
      question_id: current.id,
      selected_index: selectedIdx,
    }];
    setAnswers(newAnswers);

    if (currentIdx < questions.length - 1) {
      setTimeout(() => setCurrentIdx(i => i + 1), 300);
    } else {
      // Submit all answers
      const totalTime = (Date.now() - startTimeRef.current) / 1000;
      setSubmitting(true);
      submitDailyQuiz(newAnswers, totalTime)
        .then(result => onComplete(result))
        .catch(err => {
          setError(err.message);
          setSubmitting(false);
        });
    }
  }, [currentIdx, answers, questions, current, onComplete]);

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

  const progress = ((currentIdx + 1) / questions.length) * 100;

  return (
    <div style={{
      background: 'rgba(30,41,59,0.7)', border: '1px solid rgba(255,255,255,0.1)',
      borderRadius: 20, padding: '2rem 2.5rem',
    }}>
      {/* Progress bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>
          Question {currentIdx + 1} of {questions.length}
        </span>
        <span style={{ fontSize: '0.8rem', color: '#64748b', fontFamily: 'monospace' }}>
          {formatTime((Date.now() - startTimeRef.current) / 1000)}
        </span>
      </div>

      <div style={{
        height: 6, borderRadius: 3, background: 'rgba(255,255,255,0.08)', marginBottom: '2rem', overflow: 'hidden',
      }}>
        <div style={{
          height: '100%', borderRadius: 3, background: 'linear-gradient(90deg, #6366f1, #8b5cf6)',
          width: `${progress}%`, transition: 'width 0.4s ease',
        }} />
      </div>

      {/* Question */}
      <h3 style={{ fontSize: '1.15rem', fontWeight: 600, marginBottom: '1.5rem', lineHeight: 1.5 }}>
        {current.question_text}
      </h3>

      {/* Options */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {current.options.map((opt, idx) => (
          <button key={idx} onClick={() => handleSelect(idx)} style={{
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid rgba(255,255,255,0.12)',
            borderRadius: 12, padding: '1rem 1.25rem',
            color: '#f8fafc', fontSize: '0.95rem',
            cursor: 'pointer', textAlign: 'left',
            transition: 'all 0.15s',
            display: 'flex', alignItems: 'center', gap: '0.75rem',
          }}
            onMouseEnter={e => {
              e.currentTarget.style.background = 'rgba(99,102,241,0.15)';
              e.currentTarget.style.borderColor = 'rgba(99,102,241,0.4)';
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = 'rgba(255,255,255,0.04)';
              e.currentTarget.style.borderColor = 'rgba(255,255,255,0.12)';
            }}
          >
            <span style={{
              width: 28, height: 28, borderRadius: 8,
              background: 'rgba(255,255,255,0.08)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '0.8rem', fontWeight: 700, flexShrink: 0,
            }}>
              {String.fromCharCode(65 + idx)}
            </span>
            {opt}
          </button>
        ))}
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

  const score = result.score;
  const total = result.total_questions;
  const time = result.total_time_sec;
  const rank = result.rank;
  const review = result.review || [];

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
        <div style={{ display: 'flex', justifyContent: 'center', gap: '2rem', marginTop: '1rem' }}>
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
              {!r.is_correct && (
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
          🔒 Next quiz unlocks in{' '}
        </span>
        <CountdownTimer seconds={getTimeUntilMidnightUTC()} />
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
            review: data.user_answers,
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
        <CompletedCard quizData={quizData} result={result} />
      )}
    </div>
  );
}
