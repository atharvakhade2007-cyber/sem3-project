import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { useAuth } from './context/AuthContext';
import { useUi } from './context/UiContext';
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import { ThemeProvider } from './context/ThemeContext';
import AuthPage from './components/AuthPage';
import Profile from './components/Profile';
import ProtectedRoute from './components/ProtectedRoute';
import ErrorBoundary from './components/ErrorBoundary';
import Dashboard from './pages/Dashboard';
import HomePage from './pages/HomePage';
import LeaderboardPage from './pages/LeaderboardPage';
import QuizPage from './pages/QuizPage';

export default function App() {
  return (
    <AuthProvider>
      <ThemeProvider>
        <UiProvider>
          <BrowserRouter>
            <div className="page-shell">
              <Navbar />
              <main className="page-main">
                <ErrorBoundary>
                  <Routes>
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
                    <Route path="/quiz" element={<QuizPage />} />
                    <Route path="*" element={<Navigate to="/" replace />} />
                  </Routes>
                </ErrorBoundary>
              </main>
              <Footer />
            </div>
          </BrowserRouter>
        </UiProvider>
      </ThemeProvider>
    </AuthProvider>
  );
}