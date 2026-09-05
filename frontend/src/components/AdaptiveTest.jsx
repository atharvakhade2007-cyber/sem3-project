import { useState, useEffect, useRef, useCallback } from 'react';
import { startTest, submitAnswer, completeTest } from '../api';
import { useUi } from '../context/UiContext';
import { eloLevel } from '../constants';

// ─── State Machine States ──────────────────────
const STATES = {
  IDLE: 'IDLE',
  LOADING: 'LOADING',
  QUESTION: 'QUESTION',    // user is picking an option
  SUBMITTING: 'SUBMITTING', // answer submitted, waiting for server
  FEEDBACK: 'FEEDBACK',    // showing correct/wrong + explanation
  COMPLETE: 'COMPLETE',
  ERROR: 'ERROR',
};

// ─── Difficulty Styling ────────────────────────
const DIFF_STYLES = {
  easy: { bg: 'rgba(16,185,129,0.15)', color: '#34d399', border: 'rgba(16,185,129,0.3)' },
  medium: { bg: 'rgba(245,158,11,0.15)', color: '#fbbf24', border: 'rgba(245,158,11,0.3)' },
  hard: { bg: 'rgba(239,68,68,0.15)', color: '#fca5a5', border: 'rgba(239,68,68,0.3)' },
};

function DiffBadge({ label }) {
  const style = DIFF_STYLES[label] || DIFF_STYLES.medium;
  return (
    <span style={{
      padding: '0.3rem 0.8rem',
      borderRadius: '20px',
      fontSize: '0.8rem',
      fontWeight: 600,
      background: style.bg,
      color: style.color,
      border: `1px solid ${style.border}`,
    }}>
      {label?.charAt(0).toUpperCase() + label?.slice(1)}
    </span>
  );
}

export default function AdaptiveTest({ documentId }) {
  const { openChallengeWithSession } = useUi();
  const [state, setState] = useState(STATES.IDLE);
  const [questionCount, setQuestionCount] = useState(10);
  const [sessionId, setSessionId] = useState(null);
  const [question, setQuestion] = useState(null);
  const [selectedIndex, setSelectedIndex] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const [stats, setStats] = useState({
    answered: 0,
    correct: 0,
    wrong: 0,
    elo: 0, // 0-based Elo — new learners start at 0
    eloChange: 0,
  });
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  // The next question returned by the server while the user is still reviewing
  // the answer they just submitted. It is deliberately NOT written into
  // `question` until the user advances — the review screen must always render
  // the question that was actually answered, never a pre-loaded next one.
  const [pendingQuestion, setPendingQuestion] = useState(null);
  const questionStartTime = useRef(null);
  // Atomic guard against double-invocation of submit (Enter key auto-repeat or
  // rapid double clicks) while an answer request is in flight — otherwise the
  // same answer could be graded twice against the server.
  const submitInFlightRef = useRef(false);

  // ─── Start the test ──────────────────────────
  const handleStart = useCallback(async () => {
    setState(STATES.LOADING);
    try {
      const data = await startTest(documentId, questionCount);
      setSessionId(data.session_id);
      setStats(prev => ({ ...prev, elo: data.start_elo }));
      setQuestion(data.question);
      setPendingQuestion(null);
      setSelectedIndex(null);
      setFeedback(null);
      setError(null);
      submitInFlightRef.current = false;
      questionStartTime.current = Date.now();
      // Sync the frontend questionCount with what the backend actually accepted
      // (e.g. validator may clamp 12 -> 12, or 50 -> 50, or reject).
      if (data.questions_to_answer != null) {
        setQuestionCount(data.questions_to_answer);
      }
    } catch (err) {
      setError(err.message);
      setState(STATES.ERROR);
    }
  }, [documentId]);

  // ─── Select an option (no submit yet) ────────
  const handleSelectOption = useCallback((index) => {
    if (state !== STATES.QUESTION) return;
    setSelectedIndex(index);
  }, [state]);

  // ─── Submit the selected answer ──────────────
  const handleSubmitAnswer = useCallback(async () => {
    if (state !== STATES.QUESTION || selectedIndex === null) return;
    if (submitInFlightRef.current) return; // already submitting — ignore repeats
    submitInFlightRef.current = true;

    setState(STATES.SUBMITTING);
    const timeTaken = (Date.now() - questionStartTime.current) / 1000;

    try {
      const data = await submitAnswer(sessionId, question.id, selectedIndex, timeTaken);

      setFeedback({
        isCorrect: data.is_correct,
        correctIndex: data.correct_index,
        explanation: data.explanation,
      });

      setStats(prev => ({
        answered: data.questions_answered,
        correct: data.correct_count || prev.correct + (data.is_correct ? 1 : 0),
        wrong: (data.correct_count ? data.questions_answered - data.correct_count : prev.wrong + (data.is_correct ? 0 : 1)),
        elo: data.user_elo_after,
        eloChange: data.elo_change,
      }));

      // ── Do NOT swap `question` here. ──
      // `question` stays on the question the user just answered so the FEEDBACK
      // review (correct option + explanation) is rendered against the correct
      // question. The server's next question is stashed and only mounted when
      // handleNext performs the atomic transition.
      setPendingQuestion(data.next_question || null);

      if (data.session_completed) {
        const resultsData = await completeTest(sessionId);
        setResults(resultsData);
      }

      setState(STATES.FEEDBACK);
    } catch (err) {
      setError(err.message);
      setState(STATES.ERROR);
    } finally {
      submitInFlightRef.current = false;
    }
  }, [state, selectedIndex, sessionId, question]);

  // ─── Move to next question after feedback ────
  const handleNext = useCallback(() => {
    if (state !== STATES.FEEDBACK) return;

    // Final question — the review screen is showing the last answer, results
    // are already fetched, so go straight to the summary.
    if (results) {
      setState(STATES.COMPLETE);
      return;
    }

    // No server-provided next question and no results: nothing valid to
    // transition to. Stay on the review screen instead of corrupting state.
    if (!pendingQuestion) return;

    // ── Atomic teardown + transition ──────────────────────────
    // Mount the next question and clear every piece of the previous question's
    // review state (selection, feedback/explanation, per-question timer) in the
    // same commit. Combined with key={question.id} on the card below, the old
    // question subtree is unmounted cleanly — its feedback can never leak onto
    // the newly mounted question view.
    setQuestion(pendingQuestion);
    setPendingQuestion(null);
    setSelectedIndex(null);
    setFeedback(null);
    setError(null);
    questionStartTime.current = Date.now();
    setState(STATES.QUESTION);
  }, [state, results, pendingQuestion]);

  // ─── Keyboard shortcuts ──────────────────────
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (state === STATES.QUESTION) {
        // Select option with 1-4 or a-d
        const keyMap = { '1': 0, '2': 1, '3': 2, '4': 3, 'a': 0, 'b': 1, 'c': 2, 'd': 3 };
        const idx = keyMap[e.key.toLowerCase()];
        if (idx !== undefined) {
          handleSelectOption(idx);
        }
        // Submit with Enter (if option selected)
        if (e.key === 'Enter' && selectedIndex !== null) {
          e.preventDefault();
          handleSubmitAnswer();
        }
      } else if (state === STATES.FEEDBACK && (e.key === 'Enter' || e.key === ' ')) {
        e.preventDefault();
        handleNext();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [state, selectedIndex, handleSelectOption, handleSubmitAnswer, handleNext]);

  // ─── Render: IDLE ────────────────────────────
  if (state === STATES.IDLE) {
    const handles = {
      '10': () => setQuestionCount(10), '15': () => setQuestionCount(15),
      '20': () => setQuestionCount(20), '25': () => setQuestionCount(25),
      '30': () => setQuestionCount(30),
    };
    return (
      <div style={{ textAlign: 'center', padding: '4rem 2rem' }}>
        <h2 style={{ fontSize: '1.8rem', marginBottom: '0.75rem' }}>Adaptive Test</h2>
        <p style={{ color: '#94a3b8', maxWidth: 540, margin: '0 auto 2rem', lineHeight: 1.6 }}>
          Every new learner starts at <strong style={{ color: '#f8fafc' }}>0 Elo</strong>.
          Each answer moves your rating — <span style={{ color: '#34d399' }}>correct answers push it up (+)</span>,
          <span style={{ color: '#fca5a5' }}> wrong answers pull it down (−)</span> — and the test keeps
          serving questions at your level. Climb from Beginner to Expert!
        </p>
        <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', marginBottom: '2rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <DiffBadge label="easy" />
          <DiffBadge label="medium" />
          <DiffBadge label="hard" />
          <span style={{ color: '#64748b', fontSize: '0.8rem' }}>question difficulty</span>
        </div>
        <p style={{ color: '#cbd5e1', fontSize: '0.9rem', marginBottom: '0.5rem' }}>How many questions?</p>
        <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center', marginBottom: '2rem', flexWrap: 'wrap' }}>
          {Object.entries(handles).map(([n, onClick]) => (
            <button key={n} onClick={onClick} style={{
              padding: '0.6rem 1.4rem', borderRadius: 10, fontWeight: 700,
              cursor: 'pointer', border: `2px solid ${questionCount === Number(n) ? '#6366f1' : 'rgba(255,255,255,0.15)'}`,
              background: questionCount === Number(n) ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.04)',
              color: questionCount === Number(n) ? '#a5b4fc' : '#cbd5e1',
              transition: 'all 0.2s',
            }}>
              {n}
            </button>
          ))}
        </div>
        <button onClick={handleStart} style={{
          padding: '0.875rem 2.5rem',
          background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
          border: 'none',
          borderRadius: '10px',
          color: 'white',
          fontWeight: 600,
          fontSize: '1rem',
          cursor: 'pointer',
        }}>
          ▶ Start Test ({questionCount} questions)
        </button>
      </div>
    );
  }

  // ─── Render: LOADING / SUBMITTING ────────────
  if (state === STATES.LOADING || state === STATES.SUBMITTING) {
    return (
      <div style={{ textAlign: 'center', padding: '4rem', color: '#94a3b8' }}>
        <div style={{
          display: 'inline-block', width: 40, height: 40,
          border: '4px solid rgba(255,255,255,0.15)', borderRadius: '50%',
          borderTopColor: '#6366f1', animation: 'spin 0.8s linear infinite',
          marginBottom: '1rem',
        }} />
        <p>{state === STATES.LOADING ? 'Preparing test...' : 'Submitting answer...'}</p>
      </div>
    );
  }

  // ─── Render: COMPLETE ────────────────────────
  if (state === STATES.COMPLETE && results) {
    return (
      <div style={{ padding: '2rem' }}>
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div style={{
            display: 'inline-block', padding: '0.75rem 2rem', borderRadius: '30px',
            fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.75rem',
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', color: 'white',
          }}>
            {results.rating_badge}
          </div>
          <h2 style={{ fontSize: '1.5rem', marginBottom: '0.35rem' }}>Test Complete!</h2>
          <p style={{ color: '#94a3b8', fontSize: '0.9rem', margin: 0 }}>
            Elo journey: {Math.round(results.start_elo ?? 0)} → {Math.round(results.end_elo ?? results.final_elo ?? 0)}
            <span style={{
              fontWeight: 800, marginLeft: '0.5rem',
              color: (results.end_elo ?? results.final_elo ?? 0) >= (results.start_elo ?? 0)
                ? '#34d399' : '#fca5a5',
            }}>
              {((results.end_elo ?? results.final_elo ?? 0) >= (results.start_elo ?? 0) ? '+' : '')}
              {Math.round((results.end_elo ?? results.final_elo ?? 0) - (results.start_elo ?? 0))} Elo
            </span>
          </p>
        </div>

        {/* Challenge a friend with this exact session */}
        <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
          <button
            onClick={() => openChallengeWithSession({
              sessionId,
              label: `${results.correct_count}/${results.total_questions} correct · ${results.accuracy}% accuracy`,
            })}
            style={{
              padding: '0.8rem 1.8rem', borderRadius: 12, cursor: 'pointer',
              background: 'linear-gradient(135deg, #f59e0b, #ef4444)',
              border: 'none', color: '#fff', fontWeight: 800, fontSize: '0.95rem',
              boxShadow: '0 6px 20px rgba(245,158,11,0.35)',
            }}
          >
            ⚔️ Challenge a Friend to Beat This
          </button>
          <p style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.5rem' }}>
            A friend answers these exact {results.total_questions} questions — higher score wins, time breaks ties.
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', marginBottom: '2rem' }}>
          <div style={{ textAlign: 'center', padding: '1rem', background: 'rgba(15,23,42,0.6)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 10 }}>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#10b981' }}>{results.accuracy}%</div>
            <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '0.25rem' }}>Accuracy</div>
          </div>
          <div style={{ textAlign: 'center', padding: '1rem', background: 'rgba(15,23,42,0.6)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 10 }}>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#94a3b8' }}>{results.start_elo?.toFixed(0)}</div>
            <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '0.25rem' }}>Start Elo</div>
          </div>
          <div style={{ textAlign: 'center', padding: '1rem', background: 'rgba(15,23,42,0.6)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 10 }}>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#f59e0b' }}>{results.end_elo?.toFixed(0)}</div>
            <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '0.25rem' }}>End Elo</div>
          </div>
          <div style={{ textAlign: 'center', padding: '1rem', background: 'rgba(15,23,42,0.6)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 10 }}>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#8b5cf6' }}>{results.correct_count}/{results.total_questions}</div>
            <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '0.25rem' }}>Correct</div>
          </div>
        </div>

        <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.75rem' }}>Question Review</h3>
        <ul style={{ listStyle: 'none' }}>
          {results.breakdown?.map((item, i) => (
            <li key={i} style={{ padding: '1rem', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
              <div style={{ fontWeight: 600, marginBottom: '0.5rem' }}>Q{i + 1}. {item.question_text}</div>
              <div style={{ fontSize: '0.8rem', color: '#94a3b8', display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                <span style={{ color: item.is_correct ? '#10b981' : '#ef4444' }}>
                  {item.is_correct ? '✓ Correct' : '✗ Incorrect'}
                </span>
                <span>Your: {['A','B','C','D'][item.selected_index]} | Correct: {['A','B','C','D'][item.correct_index]}</span>
                <DiffBadge label={item.difficulty_label} />
                <span style={{ color: '#f59e0b' }}>Elo: {item.user_elo_after?.toFixed(0)}</span>
              </div>
              {item.explanation && (
                <div style={{ marginTop: '0.5rem', fontSize: '0.85rem', color: '#cbd5e1', padding: '0.5rem 0.75rem', background: 'rgba(255,255,255,0.03)', borderRadius: 6 }}>
                  {item.explanation}
                </div>
              )}
            </li>
          ))}
        </ul>
      </div>
    );
  }

  // ─── Render: ERROR ───────────────────────────
  if (state === STATES.ERROR) {
    return (
      <div style={{ textAlign: 'center', padding: '4rem', color: '#ef4444' }}>
        <p>Error: {error}</p>
        <button onClick={() => { setState(STATES.IDLE); setError(null); }} style={{
          marginTop: '1rem', padding: '0.5rem 1.5rem', background: '#6366f1', border: 'none', borderRadius: 8, color: 'white', cursor: 'pointer'
        }}>
          Try Again
        </button>
      </div>
    );
  }

  // ─── Render: QUESTION or FEEDBACK ────────────
  const isFeedback = state === STATES.FEEDBACK;
  const keys = ['A', 'B', 'C', 'D'];
  // During FEEDBACK the card still shows the just-answered question (ordinal =
  // answered count). After advancing, the fresh question is the next one
  // (ordinal = answered count + 1).
  const questionNumber = stats.answered + (isFeedback ? 0 : 1);

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 280px', gap: '1.5rem' }}>
        <div>
          {/* Progress */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem' }}>
            <div style={{ flex: 1, height: 6, background: 'rgba(255,255,255,0.1)', borderRadius: 3, overflow: 'hidden' }}>
              <div style={{
                height: '100%', background: 'linear-gradient(90deg, #6366f1, #8b5cf6)',
                borderRadius: 3, width: `${Math.min((stats.answered / questionCount) * 100, 100)}%`,
                transition: 'width 0.3s',
              }} />
            </div>
            <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Question {questionNumber} of {questionCount} ({stats.correct}C / {stats.wrong}W)</span>
          </div>

          {/* Question Card — keyed by the unique question id so React cleanly
              unmounts the previous question (and any per-question state) the
              instant we transition to the next one. */}
          <div key={question?.id} style={{
            background: 'rgba(30,41,59,0.7)', border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 16, padding: '1.5rem', boxShadow: '0 20px 40px rgba(0,0,0,0.3)',
          }}>
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <span style={{
                background: 'rgba(99,102,241,0.2)', color: '#a5b4fc', fontWeight: 700,
                fontSize: '0.8rem', padding: '0.25rem 0.6rem', borderRadius: 6,
              }}>
                Q{questionNumber}
              </span>
              <DiffBadge label={question?.difficulty_label} />
            </div>

            {/* Question text */}
            <div style={{ fontSize: '1.1rem', lineHeight: 1.6, marginBottom: '1.5rem' }}>
              {question?.question_text}
            </div>

            {/* Options — click to select (highlight), not submit */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {question?.options?.map((opt, i) => {
                const isSelected = selectedIndex === i;
                const isCorrectOption = isFeedback && i === feedback?.correctIndex;
                const isWrongSelected = isFeedback && i === selectedIndex && !feedback?.isCorrect;

                let bg = 'rgba(255,255,255,0.03)';
                let borderColor = 'rgba(255,255,255,0.1)';

                if (!isFeedback && isSelected) {
                  // Selected but not yet submitted — highlight in primary
                  bg = 'rgba(99,102,241,0.15)';
                  borderColor = '#6366f1';
                }
                if (isFeedback && isCorrectOption) {
                  bg = 'rgba(16,185,129,0.12)';
                  borderColor = '#10b981';
                }
                if (isFeedback && isWrongSelected) {
                  bg = 'rgba(239,68,68,0.12)';
                  borderColor = '#ef4444';
                }

                return (
                  <button
                    key={i}
                    onClick={() => handleSelectOption(i)}
                    disabled={isFeedback}
                    style={{
                      display: 'flex', alignItems: 'center', gap: '0.75rem',
                      padding: '0.875rem 1rem', background: bg,
                      border: `1px solid ${borderColor}`, borderRadius: 10,
                      cursor: isFeedback ? 'default' : 'pointer',
                      fontSize: '0.95rem', color: '#f8fafc', textAlign: 'left',
                      transition: 'all 0.2s', width: '100%',
                    }}
                  >
                    <span style={{
                      width: 28, height: 28, borderRadius: '50%',
                      background: isCorrectOption ? '#10b981'
                        : isWrongSelected ? '#ef4444'
                        : isSelected && !isFeedback ? '#6366f1'
                        : 'rgba(255,255,255,0.1)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontWeight: 700, fontSize: '0.8rem', flexShrink: 0,
                      color: (isCorrectOption || isWrongSelected || (isSelected && !isFeedback)) ? 'white' : undefined,
                    }}>
                      {keys[i]}
                    </span>
                    <span>{opt}</span>
                  </button>
                );
              })}
            </div>

            {/* SUBMIT BUTTON — only in QUESTION state when an option is selected */}
            {!isFeedback && selectedIndex !== null && (
              <button onClick={handleSubmitAnswer} style={{
                marginTop: '1.25rem', width: '100%',
                padding: '0.875rem', background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                border: 'none', borderRadius: 10, color: 'white',
                fontWeight: 600, fontSize: '0.95rem', cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem',
              }}>
                ✓ Submit Answer
              </button>
            )}

            {/* Hint when nothing selected */}
            {!isFeedback && selectedIndex === null && (
              <div style={{
                marginTop: '1rem', textAlign: 'center', fontSize: '0.85rem', color: '#64748b',
              }}>
                Select an option, then press <strong>Submit Answer</strong> (or Enter)
              </div>
            )}

            {/* FEEDBACK — shows after submit */}
            {isFeedback && feedback && (
              <>
                <div style={{
                  padding: '1rem', borderRadius: 10, marginTop: '1rem',
                  background: feedback.isCorrect ? 'rgba(16,185,129,0.12)' : 'rgba(239,68,68,0.12)',
                  border: `1px solid ${feedback.isCorrect ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
                  color: feedback.isCorrect ? '#34d399' : '#fca5a5', fontSize: '0.9rem',
                }}>
                  <div style={{ fontWeight: 600, fontSize: '1rem', marginBottom: '0.25rem' }}>
                    {feedback.isCorrect ? '✓ Correct!' : `✗ Incorrect — The answer is ${keys[feedback.correctIndex]}`}
                  </div>
                  {stats.eloChange !== 0 && (
                    <div style={{ fontWeight: 800, fontSize: '0.95rem', color: stats.eloChange > 0 ? '#34d399' : '#fca5a5' }}>
                      {stats.eloChange > 0 ? '▲ +' : '▼ −'}{Math.abs(stats.eloChange).toFixed(1)} Elo
                      <span style={{ fontWeight: 600, color: '#94a3b8', marginLeft: '0.6rem', fontSize: '0.8rem' }}>
                        ({Math.round(stats.elo - stats.eloChange)} → {Math.round(stats.elo)})
                      </span>
                    </div>
                  )}
                  {feedback.explanation && (
                    <div style={{ marginTop: '0.5rem', color: '#cbd5e1', lineHeight: 1.6 }}>
                      {feedback.explanation}
                    </div>
                  )}
                </div>

                <button onClick={handleNext} style={{
                  marginTop: '1rem', width: '100%',
                  padding: '0.75rem', background: results ? '#10b981' : '#6366f1',
                  border: 'none', borderRadius: 10, color: 'white',
                  fontWeight: 600, fontSize: '0.9rem', cursor: 'pointer',
                }}>
                  {results ? '📊 View Results' : 'Next Question →'}
                </button>
              </>
            )}
          </div>
        </div>

        {/* Sidebar stats */}
        <div>
          <div style={{
            background: 'rgba(30,41,59,0.7)', border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 16, padding: '1.5rem', marginBottom: '1rem',
          }}>
            <div style={{ marginBottom: '1rem' }}>
              <div style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Current Elo</div>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#f59e0b' }}>
                {stats.elo.toFixed(0)}
                {stats.eloChange !== 0 && (
                  <span style={{ fontSize: '0.8rem', color: stats.eloChange > 0 ? '#10b981' : '#ef4444', marginLeft: 8 }}>
                    {stats.eloChange > 0 ? '+' : ''}{stats.eloChange.toFixed(1)}
                  </span>
                )}
              </div>
              <div style={{ fontSize: '0.78rem', color: '#94a3b8', marginTop: '0.3rem' }}>
                Level: <span style={{ color: eloLevel(stats.elo).color, fontWeight: 800 }}>{eloLevel(stats.elo).label}</span>
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
              <span style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Correct</span>
              <span style={{ fontWeight: 700, color: '#10b981' }}>{stats.correct}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Wrong</span>
              <span style={{ fontWeight: 700, color: '#ef4444' }}>{stats.wrong}</span>
            </div>
          </div>

          <div style={{
            background: 'rgba(30,41,59,0.7)', border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 16, padding: '1rem',
          }}>
            <div style={{ fontSize: '0.8rem', color: '#64748b', lineHeight: 1.6 }}>
              <strong style={{ color: '#94a3b8' }}>Keyboard shortcuts</strong><br />
              <kbd style={kbdStyle}>1</kbd>-<kbd style={kbdStyle}>4</kbd> Select option<br />
              <kbd style={kbdStyle}>Enter</kbd> Submit / Next
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

const kbdStyle = {
  display: 'inline-block', padding: '0.1rem 0.4rem',
  background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.15)',
  borderRadius: 4, fontSize: '0.7rem', fontFamily: 'monospace', color: '#94a3b8',
};
