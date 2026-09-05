import { useState } from 'react';
import { Link } from 'react-router-dom';
import Upload from '../components/Upload';
import Summary from '../components/Summary';
import Flashcards from '../components/Flashcards';
import AdaptiveTest from '../components/AdaptiveTest';
import DailyQuiz from '../components/DailyQuiz';
import { useAuth } from '../context/AuthContext';

const VIEWS = {
  UPLOAD: 'UPLOAD',
  ACTION_SELECT: 'ACTION_SELECT',
  SUMMARY: 'SUMMARY',
  FLASHCARDS: 'FLASHCARDS',
  ADAPTIVE_TEST: 'ADAPTIVE_TEST',
};

/* ── Shared bits ─────────────────────────────────── */

function Card({ children, className = '', style, onClick, hover = false }) {
  return (
    <div
      onClick={onClick}
      className={`${className} ${hover ? 'card-hover' : ''}`}
      style={{ padding: '1.75rem', height: '100%', ...style }}
    >
      {children}
    </div>
  );
}

function BackLink({ onClick }) {
  return (
    <button
      onClick={onClick}
      className="btn btn-secondary"
      style={{ marginBottom: '1.5rem', padding: '0.55rem 1.1rem', fontSize: '0.85rem' }}
    >
      ← Back
    </button>
  );
}

function SectionHeading({ eyebrow, title, sub }) {
  return (
    <div style={{ marginBottom: '2rem' }}>
      {eyebrow && <div className="t-eyebrow rise">{eyebrow}</div>}
      <h1 className="t-headline rise rise-1" style={{ marginTop: '0.35rem' }}>
        {title}
      </h1>
      {sub && (
        <p className="t-body rise rise-2" style={{ marginTop: '0.6rem', maxWidth: 560 }}>
          {sub}
        </p>
      )}
    </div>
  );
}

/* ── Landing: asymmetric bento grid ──────────────── */

const FEATURES = [
  {
    icon: '📄',
    title: 'Smart Summary',
    body: 'A clean TL;DR, key concepts, and every term defined — generated the moment your PDF lands.',
    wash: 'wash-blue',
    span: 'span-2',
  },
  {
    icon: '🃏',
    title: 'Flashcards',
    body: 'Twenty cards, click to flip, keyboard-first. The fastest way to lock facts in.',
    wash: 'wash-purple',
    span: 'span-2',
  },
  {
    icon: '📈',
    title: 'Adaptive Test',
    body: 'Questions that adjust in real time to your Elo rating — never too easy, never brutal.',
    wash: 'wash-green',
    span: 'span-2',
  },
];

function Landing() {
  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '4rem 1.5rem 5rem' }}>
      {/* Hero */}
      <div style={{ maxWidth: 760, margin: '0 auto 4rem', textAlign: 'center' }}>
        <span className="pill rise">✦ Your AI study companion</span>
        <h1 className="t-display rise rise-1" style={{ marginTop: '1.25rem' }}>
          Study <span className="t-grad">smarter</span>,<br />
          not longer.
        </h1>
        <p
          className="t-body rise rise-2"
          style={{ margin: '1.5rem auto 0', maxWidth: 580, fontSize: '1.08rem' }}
        >
          Turn any PDF into summaries, flashcards, and an adaptive test — plus a
          daily GK quiz with a global leaderboard.
        </p>
        <div
          className="rise rise-3"
          style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center', marginTop: '2.25rem', flexWrap: 'wrap' }}
        >
          <Link to="/signup" className="btn btn-primary" style={{ padding: '0.85rem 1.9rem', fontSize: '0.98rem' }}>
            Get started — it's free
          </Link>
          <Link to="/login" className="btn btn-secondary" style={{ padding: '0.85rem 1.9rem', fontSize: '0.98rem' }}>
            Log in
          </Link>
        </div>
      </div>

      {/* Bento grid */}
      <div className="bento rise rise-2">
        {/* Hero card — large, spans 4×2 */}
        <div className="card card-hover wash-blue span-4 row-2" style={{ padding: '2.25rem', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: '2rem' }}>
          <div>
            <div className="icon-tile" style={{ width: 54, height: 54, fontSize: '1.6rem', marginBottom: '1.5rem' }}>🎓</div>
            <h2 className="t-headline">One upload.<br />Three study tools.</h2>
            <p className="t-body" style={{ marginTop: '0.9rem', maxWidth: 440 }}>
              Drop in a lecture note, a chapter, or an entire paper. StudyMind
              reads it and builds everything you need to revise it.
            </p>
          </div>
          {/* Mini stat strip */}
          <div style={{ display: 'flex', gap: '2.25rem', flexWrap: 'wrap' }}>
            {[
              ['10', 'quiz questions daily'],
              ['20', 'flashcards per PDF'],
              ['∞', 'adaptive practice'],
            ].map(([n, label]) => (
              <div key={label}>
                <div style={{ fontSize: '1.9rem', fontWeight: 700, letterSpacing: '-0.03em' }}>{n}</div>
                <div className="t-caption">{label}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Daily quiz card — tall, spans 2×2 */}
        <div className="card card-hover wash-warm span-2 row-2" style={{ padding: '2rem', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: '1.5rem' }}>
          <div>
            <div className="icon-tile">🗓️</div>
            <h3 className="t-title" style={{ marginTop: '1.1rem', fontSize: '1.2rem' }}>Daily Quiz</h3>
            <p className="t-caption" style={{ marginTop: '0.5rem' }}>
              Every day at midnight IST, a fresh 10-question challenge — headlines
              plus questions tuned to your level.
            </p>
          </div>
          <div>
            <div style={{ fontSize: '2.2rem', fontWeight: 700, letterSpacing: '-0.03em' }}>🔥</div>
            <p className="t-caption" style={{ marginTop: '0.35rem' }}>
              Keep your streak alive. Climb the global leaderboard.
            </p>
          </div>
        </div>

        {/* Feature cards — three across, each 2 wide */}
        {FEATURES.map((f, i) => (
          <div
            key={f.title}
            className={`card card-hover ${f.wash} ${f.span}`}
            style={{ padding: '1.75rem' }}
          >
            <div className="icon-tile">{f.icon}</div>
            <h3 className="t-title" style={{ marginTop: '1rem' }}>{f.title}</h3>
            <p className="t-caption" style={{ marginTop: '0.45rem' }}>{f.body}</p>
            {i === FEATURES.length - 1 && null}
          </div>
        ))}

        {/* Social card — wide strip */}
        <div className="card card-hover span-4" style={{ padding: '1.75rem', display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
          <div className="icon-tile" style={{ width: 54, height: 54 }}>🤝</div>
          <div style={{ flex: 1 }}>
            <h3 className="t-title">Learn together</h3>
            <p className="t-caption" style={{ marginTop: '0.35rem' }}>
              Add friends, compare streaks, and duel on the exact same questions.
            </p>
          </div>
          <span className="pill">⚔️ Duels</span>
        </div>

        {/* CTA card — 2 wide */}
        <div
          className="card card-hover span-2"
          style={{
            padding: '1.75rem',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'flex-start',
            justifyContent: 'center',
            gap: '0.75rem',
            background: 'var(--accent)',
            border: 'none',
          }}
        >
          <h3 className="t-title" style={{ color: 'var(--accent-contrast)', fontSize: '1.2rem' }}>Ready to start?</h3>
          <p className="t-caption" style={{ color: 'color-mix(in srgb, var(--accent-contrast) 78%, transparent)' }}>
            Your first PDF is 30 seconds away.
          </p>
          <Link
            to="/signup"
            className="btn"
            style={{ background: 'var(--accent-contrast)', color: 'var(--accent)', marginTop: '0.25rem' }}
          >
            Create account →
          </Link>
        </div>
      </div>
    </div>
  );
}

/* ── Authenticated workspace ─────────────────────── */

const ACTION_CARDS = [
  {
    key: 'SUMMARY',
    icon: '📄',
    title: 'Summary',
    body: 'TL;DR, key concepts, and terminology — generated from your document.',
    wash: 'wash-blue',
    span: 'span-4',
  },
  {
    key: 'FLASHCARDS',
    icon: '🃏',
    title: 'Flashcards',
    body: '20 interactive cards with flip animation and keyboard navigation.',
    wash: 'wash-purple',
    span: 'span-2',
  },
  {
    key: 'ADAPTIVE_TEST',
    icon: '📈',
    title: 'Adaptive Test',
    body: 'Difficulty that follows your performance in real time.',
    wash: 'wash-green',
    span: 'span-2',
  },
];

export default function Dashboard() {
  const { user, loading } = useAuth();
  const [view, setView] = useState(VIEWS.UPLOAD);
  const [documentId, setDocumentId] = useState(null);
  const [documentName, setDocumentName] = useState('');

  if (loading) {
    return (
      <div style={{ minHeight: '60vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div className="spinner" />
      </div>
    );
  }

  if (!user) {
    return <Landing />;
  }

  const handleUpload = (docId, filename) => {
    setDocumentId(docId);
    setDocumentName(filename);
    setView(VIEWS.ACTION_SELECT);
  };

  /* Action select — bento of study modes */
  if (view === VIEWS.ACTION_SELECT) {
    return (
      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '3rem 1.5rem' }}>
        <BackLink onClick={() => setView(VIEWS.UPLOAD)} />
        <SectionHeading
          eyebrow="PDF processed"
          title={documentName}
          sub="Choose how you want to study this document."
        />
        <div className="bento">
          <div
            className="card card-hover wash-blue span-4 row-2"
            onClick={() => setView(VIEWS.SUMMARY)}
            style={{ padding: '2rem', cursor: 'pointer', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: '2rem' }}
          >
            <div>
              <div className="icon-tile" style={{ width: 54, height: 54, fontSize: '1.6rem' }}>📄</div>
              <h3 className="t-headline" style={{ marginTop: '1.25rem', fontSize: '1.5rem' }}>Summary</h3>
              <p className="t-body" style={{ marginTop: '0.75rem', maxWidth: 420 }}>
                An executive TL;DR, the key concepts that matter, and every piece
                of terminology defined in plain language.
              </p>
            </div>
            <span className="btn btn-secondary" style={{ alignSelf: 'flex-start' }}>Open summary →</span>
          </div>

          <div
            className="card card-hover wash-purple span-2"
            onClick={() => setView(VIEWS.FLASHCARDS)}
            style={{ padding: '1.75rem', cursor: 'pointer' }}
          >
            <div className="icon-tile">🃏</div>
            <h3 className="t-title" style={{ marginTop: '1rem' }}>Flashcards</h3>
            <p className="t-caption" style={{ marginTop: '0.45rem' }}>
              20 cards, click to flip, arrow keys to navigate.
            </p>
          </div>

          <div
            className="card card-hover wash-green span-2"
            onClick={() => setView(VIEWS.ADAPTIVE_TEST)}
            style={{ padding: '1.75rem', cursor: 'pointer' }}
          >
            <div className="icon-tile">📈</div>
            <h3 className="t-title" style={{ marginTop: '1rem' }}>Adaptive Test</h3>
            <p className="t-caption" style={{ marginTop: '0.45rem' }}>
              Elo-driven difficulty that adjusts as you answer.
            </p>
          </div>
        </div>
      </div>
    );
  }

  /* Summary view */
  if (view === VIEWS.SUMMARY) {
    return (
      <div style={{ maxWidth: 900, margin: '0 auto', padding: '3rem 1.5rem' }}>
        <BackLink onClick={() => setView(VIEWS.ACTION_SELECT)} />
        <SectionHeading eyebrow="Summary" title={documentName} />
        <div className="card" style={{ padding: '2rem' }}>
          <Summary documentId={documentId} />
        </div>
      </div>
    );
  }

  /* Flashcards view */
  if (view === VIEWS.FLASHCARDS) {
    return (
      <div style={{ maxWidth: 900, margin: '0 auto', padding: '3rem 1.5rem' }}>
        <BackLink onClick={() => setView(VIEWS.ACTION_SELECT)} />
        <Flashcards documentId={documentId} />
      </div>
    );
  }

  /* Adaptive test view */
  if (view === VIEWS.ADAPTIVE_TEST) {
    return (
      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '3rem 1.5rem' }}>
        <BackLink onClick={() => setView(VIEWS.ACTION_SELECT)} />
        <AdaptiveTest documentId={documentId} />
      </div>
    );
  }

  /* Upload view (default home for signed-in users) */
  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '3rem 1.5rem' }}>
      <div className="bento">
        {/* Daily quiz occupies the prominent left column */}
        <div className="span-4 row-2" style={{ display: 'flex', flexDirection: 'column' }}>
          <DailyQuiz />
        </div>

        {/* Upload column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div className="card wash-teal" style={{ padding: '1.75rem' }}>
            <SectionHeading
              eyebrow="Workspace"
              title="Upload a PDF"
              sub="Summaries, flashcards, and an adaptive test — from any document."
            />
            <Upload onUpload={handleUpload} />
          </div>

          <div className="card" style={{ padding: '1.5rem 1.75rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div className="icon-tile">⚡</div>
            <p className="t-caption">
              Processing usually takes under a minute. You'll pick a study mode
              as soon as it's ready.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
