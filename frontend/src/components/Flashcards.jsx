import { useState, useEffect, useCallback } from 'react';
import { generateFlashcards } from '../api';

export default function Flashcards({ documentId }) {
  const [cards, setCards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const result = await generateFlashcards(documentId);
        setCards(result); // v2 returns the flashcard array directly
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [documentId]);

  const nextCard = useCallback(() => {
    if (currentIndex < cards.length - 1) {
      setCurrentIndex(i => i + 1);
      setIsFlipped(false);
    }
  }, [currentIndex, cards.length]);

  const prevCard = useCallback(() => {
    if (currentIndex > 0) {
      setCurrentIndex(i => i - 1);
      setIsFlipped(false);
    }
  }, [currentIndex]);

  const flipCard = useCallback(() => {
    setIsFlipped(f => !f);
  }, []);

  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === 'ArrowRight') nextCard();
      else if (e.key === 'ArrowLeft') prevCard();
      else if (e.key === ' ') { e.preventDefault(); flipCard(); }
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [nextCard, prevCard, flipCard]);

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '4rem', color: '#94a3b8' }}>
        <div style={{
          display: 'inline-block', width: 40, height: 40,
          border: '4px solid rgba(255,255,255,0.15)', borderRadius: '50%',
          borderTopColor: '#6366f1', animation: 'spin 0.8s linear infinite',
          marginBottom: '1rem',
        }} />
        <p>Generating flashcards...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ textAlign: 'center', padding: '4rem', color: '#ef4444' }}>
        <p>Error: {error}</p>
      </div>
    );
  }

  if (cards.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '4rem', color: '#94a3b8' }}>
        <p>No flashcards generated.</p>
      </div>
    );
  }

  const card = cards[currentIndex];
  const progress = ((currentIndex + 1) / cards.length) * 100;

  return (
    <div>
      <div style={{ textAlign: 'center', marginBottom: '1rem' }}>
        <p style={{ color: '#94a3b8', fontSize: '0.85rem', marginTop: '0.25rem' }}>
          <kbd style={kbdStyle}>←</kbd> <kbd style={kbdStyle}>→</kbd> navigate |
          <kbd style={kbdStyle}>Space</kbd> flip
        </p>
      </div>

      {/* Progress bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem' }}>
        <div style={{ flex: 1, height: 6, background: 'rgba(255,255,255,0.1)', borderRadius: 3, overflow: 'hidden' }}>
          <div style={{
            height: '100%', background: 'linear-gradient(90deg, #6366f1, #8b5cf6)',
            borderRadius: 3, width: `${progress}%`, transition: 'width 0.3s',
          }} />
        </div>
        <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>{currentIndex + 1} / {cards.length}</span>
      </div>

      {/* Card with flip */}
      <div
        onClick={flipCard}
        style={{
          perspective: 1200, width: '100%', maxWidth: 700, margin: '0 auto', cursor: 'pointer',
        }}
      >
        <div style={{
          width: '100%', minHeight: 350, position: 'relative',
          transition: 'transform 0.6s cubic-bezier(0.4, 0, 0.2, 1)',
          transformStyle: 'preserve-3d',
          transform: isFlipped ? 'rotateY(180deg)' : 'rotateY(0deg)',
        }}>
          {/* Front */}
          <div style={{
            position: 'absolute', inset: 0, backfaceVisibility: 'hidden',
            borderRadius: 16, background: 'rgba(30,41,59,0.7)', border: '1px solid rgba(255,255,255,0.1)',
            padding: '2.5rem', display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', textAlign: 'center',
            boxShadow: '0 20px 40px rgba(0,0,0,0.3)',
          }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#94a3b8', marginBottom: '1rem' }}>
              Question
            </div>
            <div style={{ fontSize: '1.2rem', lineHeight: 1.6, fontWeight: 500 }}>
              {card.front}
            </div>
            <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '1.5rem' }}>
              Click or press Space to reveal answer
            </div>
          </div>

          {/* Back */}
          <div style={{
            position: 'absolute', inset: 0, backfaceVisibility: 'hidden',
            transform: 'rotateY(180deg)',
            borderRadius: 16, background: 'rgba(30,41,59,0.7)', border: '1px solid rgba(255,255,255,0.1)',
            padding: '2.5rem', display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', textAlign: 'center',
            boxShadow: '0 20px 40px rgba(0,0,0,0.3)',
          }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#94a3b8', marginBottom: '1rem' }}>
              Answer
            </div>
            <div style={{ fontSize: '1.2rem', lineHeight: 1.6, fontWeight: 500, color: '#10b981' }}>
              {card.back}
            </div>
            <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '1.5rem' }}>
              Click or press Space to see question
            </div>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '1.5rem', marginTop: '2rem' }}>
        <button onClick={prevCard} disabled={currentIndex === 0} style={ctrlBtnStyle}>
          ←
        </button>
        <button onClick={flipCard} style={{ ...ctrlBtnStyle, width: 'auto', padding: '0 1.5rem', borderRadius: 10, fontWeight: 600, fontSize: '0.9rem', background: '#6366f1', border: 'none' }}>
          Flip Card
        </button>
        <button onClick={nextCard} disabled={currentIndex === cards.length - 1} style={ctrlBtnStyle}>
          →
        </button>
      </div>
    </div>
  );
}

const kbdStyle = {
  display: 'inline-block', padding: '0.15rem 0.5rem',
  background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.15)',
  borderRadius: 4, fontSize: '0.75rem', fontFamily: 'monospace', color: '#94a3b8',
};

const ctrlBtnStyle = {
  width: 50, height: 50, borderRadius: '50%',
  border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.05)',
  color: '#f8fafc', fontSize: '1.1rem', cursor: 'pointer',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
};
