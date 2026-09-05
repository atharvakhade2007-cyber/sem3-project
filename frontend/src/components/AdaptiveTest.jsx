import { useState, useEffect, useRef, useCallback } from 'react';
import { startTest, submitAnswer, completeTest } from '../api';
import { useUi } from '../context/UiContext';

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
  easy: { bg: 'color-mix(in srgb, var(--tier-easy) 12%, transparent)', color: 'var(--tier-easy)', border: 'color-mix(in srgb, var(--tier-easy) 30%, transparent)' },
  medium: { bg: 'color-mix(in srgb, var(--tier-medium) 12%, transparent)', color: 'var(--tier-medium)', border: 'color-mix(in srgb, var(--tier-medium) 30%, transparent)' },
  hard: { bg: 'color-mix(in srgb, var(--tier-hard) 12%, transparent)', color: 'var(--tier-hard)', border: 'color-mix(in srgb, var(--tier-hard) 30%, transparent)' },
};

function DiffBadge({ label }) {
  const style = DIFF_STYLES[label] || DIFF_STYLES.medium;
  return (
    <span
      style={{
        padding: '0.28rem 0.8rem',
        borderRadius: 999,
        fontSize: '0.78rem',
        fontWeight: 600,
        background: style.bg,
        color: style.color,
        border: `1px solid ${style.border}`,
      }}
    >
      {label?.charAt(0).toUpperCase() + label?.slice(1)}
    </span>
  );
}

export default function AdaptiveTest({ documentId }) {
  const { openChallengeWithSession } = useUi();
  const [state, setState] = useState(STATES.IDLE);
  const [sessionId, setSessionId] = useState(null);
  const [question, setQuestion] = useState(null);
  const [selectedIndex, setSelectedIndex] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const [stats, setStats] = useState({
    answered: 0,
    correct: 0,
    wrong: 0,
    elo: 1200,
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
      const data = await startTest(documentId);
      setSessionId(data.session_id);
      setStats(prev => ({ ...prev, elo: data.start_elo }));
      setQuestion(data.question);
      setPendingQuestion(null);
      setSelectedIndex(null);
      setFeedback(null);
      setError(null);
      submitInFlightRef.current = false;
      questionStartTime.current = Date.now();
      setState(STATES.QUESTION);
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
    return (
      <div className="card rise" style={{ textAlign: 'center', padding: '3.5rem 2rem' }}>
        <div className="icon-tile" style={{ width: 54, height: 54, margin: '0 auto 1.4rem', fontSize: '1.5rem' }}>
          📈
        </div>
        <h2 className="t-headline">Adaptive Test</h2>
        <p className="t-body" style={{ maxWidth: 500, margin: '0.9rem auto 1.75rem' }}>
          This test adapts to your performance. Answer correctly to face harder questions,
          or drop down if you struggle. Powered by continuous Online Learning Elo.
        </p>
        <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', marginBottom: '2rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
            <DiffBadge label="easy" />
            <span className="t-caption">900 Elo seed</span>
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
            <DiffBadge label="medium" />
            <span className="t-caption">1300 Elo seed</span>
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
            <DiffBadge label="hard" />
            <span className="t-caption">1700 Elo seed</span>
          </span>
        </div>
        <button onClick={handleStart} className="btn btn-primary" style={{ padding: '0.9rem 2.4rem', fontSize: '0.98rem' }}>
          ▶ Start Test
        </button>
      </div>
    );
  }

  // ─── Render: LOADING / SUBMITTING ────────────
  if (state === STATES.LOADING || state === STATES.SUBMITTING) {
    return (
      <div style={{ textAlign: 'center', padding: '4rem', color: 'var(--text-secondary)' }}>
        <div className="spinner" style={{ margin: '0 auto 1rem' }} />
        <p className="t-body">{state === STATES.LOADING ? 'Preparing test...' : 'Submitting answer...'}</p>
      </div>
    );
  }

  // ─── Render: COMPLETE ────────────────────────
  if (state === STATES.COMPLETE && results) {
    return (
      <div>
        <div className="card wash-blue" style={{ padding: '2.5rem', textAlign: 'center', marginBottom: '14px' }}>
          <div
            style={{
              display: 'inline-block',
              padding: '0.7rem 1.9rem',
              borderRadius: 999,
              fontSize: '1.4rem',
              fontWeight: 700,
              marginBottom: '0.9rem',
              background: 'var(--accent)',
              color: 'var(--accent-contrast)',
            }}
          >
            {results.rating_badge}
          </div>
          <h2 className="t-headline">Test Complete!</h2>

          {/* Challenge a friend with this exact session */}
          <div style={{ marginTop: '1.5rem', marginBottom: '1.75rem' }}>
            <button
              onClick={() => openChallengeWithSession({
                sessionId,
                label: `${results.correct_count}/${results.total_questions} correct · ${results.accuracy}% accuracy`,
              })}
              className="btn"
              style={{
                background: 'var(--accent)',
                color: 'var(--accent-contrast)',
                fontWeight: 700,
                padding: '0.8rem 1.7rem',
                boxShadow: '0 6px 18px color-mix(in srgb, var(--accent) 30%, transparent)',
              }}
            >
              ⚔️ Challenge a Friend to Beat This
            </button>
            <p className="t-caption" style={{ fontSize: '0.76rem', marginTop: '0.6rem', color: 'var(--text-muted)' }}>
              A friend answers these exact {results.total_questions} questions — higher score wins, time breaks ties.
            </p>
          </div>

          <div className="bento" style={{ textAlign: 'center' }}>
            <div className="span-2 card" style={{ padding: '1.25rem' }}>
              <div style={{ fontSize: '1.6rem', fontWeight: 700, color: 'var(--success)', letterSpacing: '-0.03em' }}>{results.accuracy}%</div>
              <div className="t-caption" style={{ marginTop: '0.25rem', fontSize: '0.78rem' }}>Accuracy</div>
            </div>
            <div className="span-2 card" style={{ padding: '1.25rem' }}>
              <div style={{ fontSize: '1.6rem', fontWeight: 700, color: 'var(--streak)', letterSpacing: '-0.03em' }}>{results.end_elo?.toFixed(0)}</div>
              <div className="t-caption" style={{ marginTop: '0.25rem', fontSize: '0.78rem' }}>Final Elo</div>
            </div>
            <div className="span-2 card" style={{ padding: '1.25rem' }}>
              <div style={{ fontSize: '1.6rem', fontWeight: 700, color: 'var(--plum)', letterSpacing: '-0.03em' }}>{results.correct_count}/{results.total_questions}</div>
              <div className="t-caption" style={{ marginTop: '0.25rem', fontSize: '0.78rem' }}>Correct</div>
            </div>
          </div>
        </div>

        <div className="card" style={{ padding: '2rem' }}>
          <h3 className="t-title" style={{ marginBottom: '0.9rem' }}>Question Review</h3>
          <ul style={{ listStyle: 'none' }}>
            {results.breakdown?.map((item, i) => (
              <li key={i} style={{ padding: '1.1rem 0', borderBottom: '1px solid var(--card-border)' }}>
                <div style={{ fontWeight: 600, marginBottom: '0.5rem', fontSize: '0.95rem', lineHeight: 1.5 }}>
                  Q{i + 1}. {item.question_text}
                </div>
                <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', display: 'flex', gap: '0.9rem', flexWrap: 'wrap', alignItems: 'center' }}>
                  <span style={{ color: item.is_correct ? 'var(--success)' : 'var(--danger)', fontWeight: 600 }}>
                    {item.is_correct ? '✓ Correct' : '✗ Incorrect'}
                  </span>
                  <span>
                    Your: {['A', 'B', 'C', 'D'][item.selected_index]} · Correct: {['A', 'B', 'C', 'D'][item.correct_index]}
                  </span>
                  <DiffBadge label={item.difficulty_label} />
                  <span style={{ color: 'var(--streak)' }}>Elo: {item.user_elo_after?.toFixed(0)}</span>
                </div>
                {item.explanation && (
                  <div
                    style={{
                      marginTop: '0.6rem',
                      fontSize: '0.86rem',
                      color: 'var(--text-secondary)',
                      padding: '0.6rem 0.9rem',
                      background: 'var(--input-bg)',
                      borderRadius: 'var(--radius-sm)',
                      lineHeight: 1.55,
                    }}
                  >
                    {item.explanation}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      </div>
    );
  }

  // ─── Render: ERROR ───────────────────────────
  if (state === STATES.ERROR) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '4rem', color: 'var(--danger)' }}>
        <p>Error: {error}</p>
        <button
          onClick={() => { setState(STATES.IDLE); setError(null); }}
          className="btn btn-secondary"
          style={{ marginTop: '1rem' }}
        >
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
    <div className="bento">
      <div className="span-4">
        {/* Progress */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.25rem' }}>
          <div className="progress-track" style={{ flex: 1 }}>
            <div
              className="progress-fill"
              style={{ width: `${(stats.answered / Math.max(stats.answered + 1, 5)) * 100}%` }}
            />
          </div>
          <span className="t-caption" style={{ fontSize: '0.85rem' }}>{stats.answered} answered</span>
        </div>

        {/* Question Card — keyed by the unique question id so React cleanly
            unmounts the previous question (and any per-question state) the
            instant we transition to the next one. */}
        <div
          key={question?.id}
          className="card rise"
          style={{ padding: '1.75rem', boxShadow: 'var(--shadow-raised)' }}
        >
          {/* Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.1rem' }}>
            <span
              style={{
                background: 'var(--accent-soft)',
                color: 'var(--accent)',
                fontWeight: 700,
                fontSize: '0.8rem',
                padding: '0.25rem 0.7rem',
                borderRadius: 999,
              }}
            >
              Q{questionNumber}
            </span>
            <DiffBadge label={question?.difficulty_label} />
          </div>

          {/* Question text */}
          <div style={{ fontSize: '1.15rem', lineHeight: 1.6, marginBottom: '1.6rem', fontWeight: 550, letterSpacing: '-0.015em' }}>
            {question?.question_text}
          </div>

          {/* Options — click to select (highlight), not submit */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.7rem' }}>
            {question?.options?.map((opt, i) => {
              const isSelected = selectedIndex === i;
              const isCorrectOption = isFeedback && i === feedback?.correctIndex;
              const isWrongSelected = isFeedback && i === selectedIndex && !feedback?.isCorrect;

              let bg = 'var(--input-bg)';
              let borderColor = 'var(--card-border)';

              if (!isFeedback && isSelected) {
                // Selected but not yet submitted — highlight in primary
                bg = 'var(--accent-soft)';
                borderColor = 'var(--accent)';
              }
              if (isFeedback && isCorrectOption) {
                bg = 'color-mix(in srgb, var(--success) 10%, transparent)';
                borderColor = 'var(--success)';
              }
              if (isFeedback && isWrongSelected) {
                bg = 'color-mix(in srgb, var(--danger) 10%, transparent)';
                borderColor = 'var(--danger)';
              }

              return (
                <button
                  key={i}
                  onClick={() => handleSelectOption(i)}
                  disabled={isFeedback}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.8rem',
                    padding: '0.9rem 1.1rem',
                    background: bg,
                    border: `1px solid ${borderColor}`,
                    borderRadius: 'var(--radius-sm)',
                    cursor: isFeedback ? 'default' : 'pointer',
                    fontSize: '0.95rem',
                    fontFamily: 'inherit',
                    color: 'var(--text)',
                    textAlign: 'left',
                    transition: 'background 0.2s, border-color 0.2s',
                    width: '100%',
                  }}
                >
                  <span
                    style={{
                      width: 28,
                      height: 28,
                      borderRadius: '50%',
                      background: isCorrectOption
                        ? 'var(--success)'
                        : isWrongSelected
                          ? 'var(--danger)'
                          : isSelected && !isFeedback
                            ? 'var(--accent)'
                            : 'var(--input-bg)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontWeight: 700,
                      fontSize: '0.78rem',
                      flexShrink: 0,
                      color: (isCorrectOption || isWrongSelected) ? 'white' : (isSelected && !isFeedback) ? 'var(--accent-contrast)' : 'var(--text-secondary)',
                    }}
                  >
                    {keys[i]}
                  </span>
                  <span>{opt}</span>
                </button>
              );
            })}
          </div>

          {/* SUBMIT BUTTON — only in QUESTION state when an option is selected */}
          {!isFeedback && selectedIndex !== null && (
            <button
              onClick={handleSubmitAnswer}
              className="btn btn-primary rise"
              style={{ marginTop: '1.3rem', width: '100%', padding: '0.85rem' }}
            >
              ✓ Submit Answer
            </button>
          )}

          {/* Hint when nothing selected */}
          {!isFeedback && selectedIndex === null && (
            <div style={{ marginTop: '1.1rem', textAlign: 'center', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Select an option, then press <strong>Submit Answer</strong> (or Enter)
            </div>
          )}

          {/* FEEDBACK — shows after submit */}
          {isFeedback && feedback && (
            <>
              <div
                style={{
                  padding: '1.1rem 1.25rem',
                  borderRadius: 'var(--radius-md)',
                  marginTop: '1.2rem',
                  background: feedback.isCorrect ? 'color-mix(in srgb, var(--success) 10%, transparent)' : 'color-mix(in srgb, var(--danger) 10%, transparent)',
                  border: `1px solid ${feedback.isCorrect ? 'color-mix(in srgb, var(--success) 30%, transparent)' : 'color-mix(in srgb, var(--danger) 30%, transparent)'}`,
                  color: feedback.isCorrect ? 'var(--success)' : 'var(--danger)',
                  fontSize: '0.92rem',
                }}
              >
                <div style={{ fontWeight: 700, fontSize: '0.98rem', marginBottom: '0.3rem' }}>
                  {feedback.isCorrect ? '✓ Correct!' : `✗ Incorrect — The answer is ${keys[feedback.correctIndex]}`}
                </div>
                {feedback.explanation && (
                  <div style={{ marginTop: '0.4rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                    {feedback.explanation}
                  </div>
                )}
              </div>

              <button
                onClick={handleNext}
                className="btn btn-primary"
                style={{ marginTop: '1.1rem', width: '100%', padding: '0.75rem' }}
              >
                {results ? '📊 View Results' : 'Next Question →'}
              </button>
            </>
          )}
        </div>
      </div>

      {/* Sidebar stats */}
      <div className="span-2" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        <div className="card" style={{ padding: '1.5rem' }}>
          <div style={{ marginBottom: '1.1rem' }}>
            <div className="t-caption">Current Elo</div>
            <div style={{ fontSize: '1.6rem', fontWeight: 700, color: 'var(--streak)', letterSpacing: '-0.03em', fontVariantNumeric: 'tabular-nums' }}>
              {stats.elo.toFixed(0)}
              {stats.eloChange !== 0 && (
                <span
                  style={{
                    fontSize: '0.8rem',
                    color: stats.eloChange > 0 ? 'var(--success)' : 'var(--danger)',
                    marginLeft: 8,
                  }}
                >
                  {stats.eloChange > 0 ? '+' : ''}{stats.eloChange.toFixed(1)}
                </span>
              )}
            </div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
            <span className="t-caption">Correct</span>
            <span style={{ fontWeight: 700, color: 'var(--success)' }}>{stats.correct}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span className="t-caption">Wrong</span>
            <span style={{ fontWeight: 700, color: 'var(--danger)' }}>{stats.wrong}</span>
          </div>
        </div>

        <div className="card" style={{ padding: '1.25rem 1.5rem' }}>
          <div className="t-caption" style={{ lineHeight: 1.9, fontSize: '0.8rem' }}>
            <strong style={{ color: 'var(--text)', fontWeight: 650 }}>Keyboard shortcuts</strong>
            <br />
            <kbd className="kbd">1</kbd>–<kbd className="kbd">4</kbd> Select option
            <br />
            <kbd className="kbd">Enter</kbd> Submit / Next
          </div>
        </div>
      </div>
    </div>
  );
}
