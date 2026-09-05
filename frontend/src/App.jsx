import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { UiProvider } from './context/UiContext';
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import AuthPage from './components/AuthPage';
import Profile from './components/Profile';
import ProtectedRoute from './components/ProtectedRoute';
import ErrorBoundary from './components/ErrorBoundary';
import Dashboard from './pages/Dashboard';
import HomePage from './pages/HomePage';
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
            <ErrorBoundary>
            <Routes>
              {/* Daily Quiz is the home tab; the PDF Workspace lives at /workspace */}
              <Route path="/" element={<HomePage />} />
              <Route path="/workspace" element={<Dashboard />} />
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
              <Route path="/quiz" element={<Navigate to="/" replace />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
            </ErrorBoundary>
          </main>
          <Footer />
        </div>
      </BrowserRouter>
      </UiProvider>
    </AuthProvider>
  );
}