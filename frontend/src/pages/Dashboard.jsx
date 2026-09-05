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

function ActionCard({ icon, title, description, color, onClick }) {
  return (
    <div onClick={onClick} style={{
      background: 'rgba(30,41,59,0.7)', border: '1px solid rgba(255,255,255,0.1)',
      borderRadius: 16, padding: '2rem', textAlign: 'center', cursor: 'pointer',
      transition: 'transform 0.2s, box-shadow 0.2s',
      display: 'flex', flexDirection: 'column', alignItems: 'center',
    }}
    onMouseEnter={(e) => {
      e.currentTarget.style.transform = 'translateY(-4px)';
      e.currentTarget.style.boxShadow = '0 12px 30px rgba(0,0,0,0.4)';
    }}
    onMouseLeave={(e) => {
      e.currentTarget.style.transform = 'none';
      e.currentTarget.style.boxShadow = 'none';
    }}
    >
      <div style={{
        width: 72, height: 72, borderRadius: '50%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: '2rem', marginBottom: '1.25rem',
        background: `${color}15`,
      }}>
        {icon}
      </div>
      <h3 style={{ fontSize: '1.15rem', marginBottom: '0.5rem' }}>{title}</h3>
      <p style={{ fontSize: '0.85rem', color: '#94a3b8', lineHeight: 1.5, marginBottom: '1.25rem' }}>
        {description}
      </p>
      <span style={{
        padding: '0.6rem 1.5rem', borderRadius: 8, fontWeight: 600, fontSize: '0.85rem',
        background: `linear-gradient(135deg, ${color}, ${color}cc)`, color: 'white',
      }}>
        Select
      </span>
    </div>
  );
}

function LandingHero() {
  return (
    <div style={{
      maxWidth: 700, margin: '3rem auto', textAlign: 'center',
    }}>
      <div style={{ fontSize: '4rem', marginBottom: '1rem' }}>🎓</div>
      <h1 style={{ fontSize: '2.4rem', fontWeight: 800, marginBottom: '0.75rem' }}>
        AI-Powered Study Companion
      </h1>
      <p style={{ color: 'var(--text-secondary)', fontSize: '1.05rem', lineHeight: 1.6, marginBottom: '2rem' }}>
        Upload a PDF to unlock intelligent study tools — summaries, flashcards,
        and adaptive testing — plus a daily GK quiz with global leaderboards.
        Sign in to start learning.
      </p>
      <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap' }}>
        <Link to="/login" style={{
          background: 'var(--card-bg)', border: '1px solid var(--card-border)',
          color: 'var(--text)', textDecoration: 'none',
          borderRadius: 12, padding: '0.8rem 2rem', fontWeight: 700,
        }}>
          Log In
        </Link>
        <Link to="/signup" style={{
          background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
          color: '#fff', textDecoration: 'none',
          borderRadius: 12, padding: '0.8rem 2rem', fontWeight: 700,
          boxShadow: '0 4px 18px rgba(99,102,241,0.4)',
        }}>
          Get Started — It's Free
        </Link>
      </div>
      <div style={{
        display: 'inline-flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap',
        marginTop: '2.5rem',
      }}>
        {['📄 Smart Summary', '🃏 Flashcards', '📈 Adaptive Test', '🗓️ Daily Quiz'].map(label => (
          <span key={label} style={{
            background: 'var(--card-bg)', border: '1px solid var(--card-border)',
            color: 'var(--text-secondary)', padding: '0.5rem 1rem', borderRadius: 20, fontSize: '0.85rem',
          }}>
            ✅ {label}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { user, loading } = useAuth();
  const [view, setView] = useState(VIEWS.UPLOAD);
  const [documentId, setDocumentId] = useState(null);
  const [documentName, setDocumentName] = useState('');

  if (loading) {
    return (
      <div style={{ minHeight: '60vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{
          width: 40, height: 40,
          border: '3px solid rgba(99,102,241,0.3)', borderTopColor: '#6366f1',
          borderRadius: '50%', animation: 'spin 0.8s linear infinite',
        }} />
      </div>
    );
  }

  if (!user) {
    return (
      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 1.5rem' }}>
        <LandingHero />
      </div>
    );
  }

  const handleUpload = (docId, filename) => {
    setDocumentId(docId);
    setDocumentName(filename);
    setView(VIEWS.ACTION_SELECT);
  };

  const BackLink = ({ onClick }) => (
    <button onClick={onClick} style={{
      display: 'inline-flex', alignItems: 'center', gap: '0.5rem',
      color: '#94a3b8', background: 'none', border: 'none', cursor: 'pointer',
      fontSize: '0.9rem', marginBottom: '1.5rem', padding: 0,
    }}>
      ← Back
    </button>
  );

  return (
    <div style={{ maxWidth: 1200, margin: '2rem auto', padding: '0 1.5rem' }}>
      {/* Daily Quiz Hero — always visible on homepage */}
      {view === VIEWS.UPLOAD && (
        <div style={{ marginBottom: '2rem' }}>
          <DailyQuiz />
        </div>
      )}

      {/* Upload View */}
      {view === VIEWS.UPLOAD && (
        <div style={{ display: 'grid', gridTemplateColumns: '380px 1fr', gap: '2rem' }}>
          <div style={{
            background: 'rgba(30,41,59,0.7)', border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 16, padding: '1.5rem',
          }}>
            <Upload onUpload={handleUpload} />
          </div>
          <div style={{
            background: 'rgba(30,41,59,0.7)', border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 16, padding: '3rem 2rem', textAlign: 'center',
          }}>
            <div style={{ fontSize: '3.5rem', color: '#6366f1', marginBottom: '1.25rem' }}>🎓</div>
            <h2 style={{ fontSize: '1.5rem', marginBottom: '0.75rem' }}>AI-Powered Study Companion</h2>
            <p style={{ color: '#94a3b8', maxWidth: 560, margin: '0 auto 2rem', fontSize: '0.95rem', lineHeight: 1.6 }}>
              Upload a PDF to unlock intelligent study tools — summaries, flashcards, and adaptive testing that learns your level.
            </p>
            <div style={{ display: 'inline-flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap' }}>
              {['📄 Smart Summary', '🃏 Flashcards', '📈 Adaptive Test'].map((label) => (
                <span key={label} style={{
                  background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
                  color: '#cbd5e1', padding: '0.5rem 1rem', borderRadius: 20, fontSize: '0.85rem',
                }}>
                  ✅ {label}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Action Select */}
      {view === VIEWS.ACTION_SELECT && (
        <div style={{ maxWidth: 900, margin: '0 auto' }}>
          <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
            <div style={{ fontSize: '2rem', color: '#6366f1', marginBottom: '0.75rem' }}>✅</div>
            <h2 style={{ fontSize: '1.5rem', marginBottom: '0.25rem' }}>{documentName}</h2>
            <p style={{ color: '#94a3b8', fontSize: '0.9rem' }}>PDF processed. Choose your study mode below.</p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1.5rem' }}>
            <ActionCard
              icon="📄"
              title="Summary"
              description="Auto-generated TL;DR, key concepts, and terminology definitions."
              color="#6366f1"
              onClick={() => setView(VIEWS.SUMMARY)}
            />
            <ActionCard
              icon="🃏"
              title="Flashcards"
              description="20 interactive flashcards with click-to-flip and keyboard navigation."
              color="#8b5cf6"
              onClick={() => setView(VIEWS.FLASHCARDS)}
            />
            <ActionCard
              icon="📈"
              title="Adaptive Test"
              description="Dynamic difficulty quiz powered by continuous Online Learning Elo."
              color="#10b981"
              onClick={() => setView(VIEWS.ADAPTIVE_TEST)}
            />
          </div>

          <div style={{ textAlign: 'center', marginTop: '2rem' }}>
            <button onClick={() => setView(VIEWS.UPLOAD)} style={{
              color: '#94a3b8', background: 'none', border: 'none', cursor: 'pointer', fontSize: '0.9rem',
            }}>
              ← Back to Dashboard
            </button>
          </div>
        </div>
      )}

      {/* Summary */}
      {view === VIEWS.SUMMARY && (
        <div style={{ maxWidth: 900, margin: '0 auto' }}>
          <BackLink onClick={() => setView(VIEWS.ACTION_SELECT)} />
          <div style={{
            background: 'rgba(30,41,59,0.7)', border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 16, padding: '1.5rem',
          }}>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 600, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              📄 Summary — {documentName}
            </h2>
            <Summary documentId={documentId} />
          </div>
        </div>
      )}

      {/* Flashcards */}
      {view === VIEWS.FLASHCARDS && (
        <div style={{ maxWidth: 900, margin: '0 auto' }}>
          <BackLink onClick={() => setView(VIEWS.ACTION_SELECT)} />
          <Flashcards documentId={documentId} />
        </div>
      )}

      {/* Adaptive Test */}
      {view === VIEWS.ADAPTIVE_TEST && (
        <div style={{ maxWidth: 1100, margin: '0 auto' }}>
          <BackLink onClick={() => setView(VIEWS.ACTION_SELECT)} />
          <AdaptiveTest documentId={documentId} />
        </div>
      )}
    </div>
  );
}