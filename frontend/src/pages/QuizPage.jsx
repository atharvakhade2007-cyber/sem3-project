import DailyQuiz from '../components/DailyQuiz';

export default function QuizPage() {
  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '2rem 1.5rem' }}>
      <h1 style={{ fontSize: '1.6rem', fontWeight: 800, marginBottom: '1rem' }}>
        🗓️ Daily Quiz
      </h1>
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
        Five questions from today's headlines + five tuned to your GK level. Play daily to keep your streak alive!
      </p>
      <DailyQuiz />
    </div>
  );
}