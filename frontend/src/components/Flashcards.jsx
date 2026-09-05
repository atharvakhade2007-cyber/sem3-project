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
        setCards(result.flashcards);
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
      <div style={{ textAlign: 'center', padding: '4rem', color: 'var(--text-secondary)' }}>
        <div className="spinner" style={{ margin: '0 auto 1rem' }} />
        <p className="t-body">Generating flashcards...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ textAlign: 'center', padding: '4rem', color: 'var(--danger)' }}>
        <p>Error: {error}</p>
      </div>
    );
  }

  if (cards.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '4rem', color: 'var(--text-secondary)' }}>
        <p>No flashcards generated.</p>
      </div>
    );
  }

  const card = cards[currentIndex];
  const progress = ((currentIndex + 1) / cards.length) * 100;

  return (
    <div>
      <div style={{ textAlign: 'center', marginBottom: '1rem' }}>
        <p className="t-caption" style={{ fontSize: '0.8rem' }}>
          <kbd className="kbd">←</kbd> <kbd className="kbd">→</kbd> navigate ·{' '}
          <kbd className="kbd">Space</kbd> flip
        </p>
      </div>

      {/* Progress bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '2rem' }}>
        <div className="progress-track" style={{ flex: 1 }}>
          <div className="progress-fill" style={{ width: `${progress}%` }} />
        </div>
        <span className="t-caption" style={{ fontSize: '0.85rem', fontVariantNumeric: 'tabular-nums' }}>
          {currentIndex + 1} / {cards.length}
        </span>
      </div>

      {/* Card with flip */}
      <div
        onClick={flipCard}
        style={{
          perspective: 1200,
          width: '100%',
          maxWidth: 700,
          margin: '0 auto',
          cursor: 'pointer',
        }}
      >
        <div
          style={{
            width: '100%',
            minHeight: 350,
            position: 'relative',
            transition: 'transform 0.6s cubic-bezier(0.22, 1, 0.36, 1)',
            transformStyle: 'preserve-3d',
            transform: isFlipped ? 'rotateY(180deg)' : 'rotateY(0deg)',
          }}
        >
          {/* Front */}
          <div
            className="card"
            style={{
              position: 'absolute',
              inset: 0,
              backfaceVisibility: 'hidden',
              borderRadius: 'var(--radius-xl)',
              padding: '2.5rem',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              textAlign: 'center',
              boxShadow: 'var(--shadow-raised)',
            }}
          >
            <div className="t-eyebrow" style={{ marginBottom: '1.1rem' }}>
              Question
            </div>
            <div style={{ fontSize: '1.25rem', lineHeight: 1.6, fontWeight: 550, letterSpacing: '-0.015em', maxWidth: 520 }}>
              {card.front}
            </div>
            <div className="t-caption" style={{ fontSize: '0.8rem', marginTop: '1.5rem', color: 'var(--text-muted)' }}>
              Click or press Space to reveal answer
            </div>
          </div>

          {/* Back */}
          <div
            className="card wash-green"
            style={{
              position: 'absolute',
              inset: 0,
              backfaceVisibility: 'hidden',
              transform: 'rotateY(180deg)',
              borderRadius: 'var(--radius-xl)',
              padding: '2.5rem',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              textAlign: 'center',
              boxShadow: 'var(--shadow-raised)',
            }}
          >
            <div className="t-eyebrow" style={{ marginBottom: '1.1rem' }}>
              Answer
            </div>
            <div style={{ fontSize: '1.25rem', lineHeight: 1.6, fontWeight: 550, letterSpacing: '-0.015em', color: 'var(--success)', maxWidth: 520 }}>
              {card.back}
            </div>
            <div className="t-caption" style={{ fontSize: '0.8rem', marginTop: '1.5rem', color: 'var(--text-muted)' }}>
              Click or press Space to see question
            </div>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '1.5rem', marginTop: '2.25rem' }}>
        <button
          onClick={prevCard}
          disabled={currentIndex === 0}
          className="btn btn-secondary"
          style={{
            width: 50,
            height: 50,
            borderRadius: '50%',
            padding: 0,
            opacity: currentIndex === 0 ? 0.35 : 1,
            cursor: currentIndex === 0 ? 'not-allowed' : 'pointer',
            fontSize: '1.05rem',
          }}
        >
          ←
        </button>
        <button onClick={flipCard} className="btn btn-primary" style={{ padding: '0.65rem 1.6rem' }}>
          Flip Card
        </button>
        <button
          onClick={nextCard}
          disabled={currentIndex === cards.length - 1}
          className="btn btn-secondary"
          style={{
            width: 50,
            height: 50,
            borderRadius: '50%',
            padding: 0,
            opacity: currentIndex === cards.length - 1 ? 0.35 : 1,
            cursor: currentIndex === cards.length - 1 ? 'not-allowed' : 'pointer',
            fontSize: '1.05rem',
          }}
        >
          →
        </button>
      </div>
    </div>
  );
}
