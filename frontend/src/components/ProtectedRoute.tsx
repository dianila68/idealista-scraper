import { Navigate } from 'react-router-dom';
import { useMe } from '../hooks/useAuth';

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { data: user, isLoading } = useMe();
  if (isLoading) return <div className="spinner" />;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
