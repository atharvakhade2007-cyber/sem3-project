import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div style={{
        minHeight: '60vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        <div style={{
          width: 40,
          height: 40,
          border: '3px solid rgba(99,102,241,0.3)',
          borderTopColor: '#6366f1',
          borderRadius: '50%',
          animation: 'spin 0.8s linear infinite',
        }} />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  return children;
}