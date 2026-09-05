import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { UiProvider } from './context/UiContext';
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import AuthPage from './components/AuthPage';
import Profile from './components/Profile';
import ProtectedRoute from './components/ProtectedRoute';
import Dashboard from './pages/Dashboard';
import QuizPage from './pages/QuizPage';
import LeaderboardPage from './pages/LeaderboardPage';

export default function App() {
  return (
    <AuthProvider>
      <UiProvider>
      <BrowserRouter>
        <div style={{
          fontFamily: "'Plus Jakarta Sans', sans-serif",
          background: 'var(--bg-gradient)',
          color: 'var(--text)',
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
        }}>
          <Navbar />
          <main style={{ flex: 1 }}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/quiz" element={<QuizPage />} />
              <Route path="/leaderboard" element={<LeaderboardPage />} />
              <Route path="/login" element={<AuthPage mode="login" />} />
              <Route path="/signup" element={<AuthPage mode="signup" />} />
              <Route
                path="/profile"
                element={
                  <ProtectedRoute>
                    <Profile />
                  </ProtectedRoute>
                }
              />
              {/* Catch-all → dashboard */}
              <Route path="*" element={<Dashboard />} />
            </Routes>
          </main>
          <Footer />
        </div>
      </BrowserRouter>
      </UiProvider>
    </AuthProvider>
  );
}