import DailyQuiz from '../components/DailyQuiz';

export default function QuizPage() {
  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '3rem 1.5rem' }}>
      <div className="t-eyebrow rise">Every day · 10 questions</div>
      <h1 className="t-headline rise rise-1" style={{ marginTop: '0.35rem' }}>
        🗓️ Daily Quiz
      </h1>
      <p className="t-body rise rise-2" style={{ marginTop: '0.6rem', maxWidth: 560, marginBottom: '2rem' }}>
        Five questions from today's headlines, five tuned to your GK level.
        Play daily to keep your streak alive.
      </p>
      <div className="rise rise-3">
        <DailyQuiz />
      </div>
    </div>
  );
}
