import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { UiProvider } from './context/UiContext';
import Navbar from './components/Navbar';
import AuthPage from './components/AuthPage';
import Profile from './components/Profile';
import ProtectedRoute from './components/ProtectedRoute';
import ErrorBoundary from './components/ErrorBoundary';
import HomePage from './pages/HomePage';
import LeaderboardPage from './pages/LeaderboardPage';
import AdaptiveTest from './components/AdaptiveTest';

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
            <ErrorBoundary>
            <Routes>
              {/* Landing + marketing for visitors; PDF workspace for signed-in users */}
              <Route path="/" element={<HomePage />} />
              <Route path="/workspace" element={<HomePage />} />
              {/* Adaptive quiz — pick a document to start; 404 if no docId given */}
              <Route path="/quiz" element={<AdaptiveTest documentId={null} />} />
              <Route path="/quiz/:documentId" element={<AdaptiveTest documentId={null} />} />
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
              {/* Legacy/unknown URLs → home */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
            </ErrorBoundary>
          </main>
        </div>
      </BrowserRouter>
      </UiProvider>
    </AuthProvider>
  );
}