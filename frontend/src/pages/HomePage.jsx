import { useAuth } from '../context/AuthContext';
import LandingHero from '../components/LandingHero';
import QuizPage from './QuizPage';

/**
 * Home ("/"): the Daily Quiz tab for signed-in users; the marketing landing
 * page for visitors. The PDF Workspace has its own tab at /workspace.
 */
export default function HomePage() {
  const { user, loading } = useAuth();

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
    return <LandingHero />;
  }

  return <QuizPage />;
}
