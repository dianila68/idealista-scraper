import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Navbar } from './components/Navbar';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Login } from './pages/Login';
import { Register } from './pages/Register';
import { ForgotPassword } from './pages/ForgotPassword';
import { ResetPassword } from './pages/ResetPassword';
import { Listings } from './pages/Listings';
import { MapView } from './pages/MapView';
import { Filters } from './pages/Filters';
import { Profile } from './pages/Profile';
import './styles/global.css';

const qc = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Routes>
          {/* Public routes — no navbar */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />

          {/* Protected routes — with navbar */}
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <div className="main-layout">
                  <Navbar />
                  <Routes>
                    <Route path="/" element={<Navigate to="/listings" replace />} />
                    <Route
                      path="/listings"
                      element={<div className="page-body"><Listings /></div>}
                    />
                    <Route path="/map" element={<MapView />} />
                    <Route
                      path="/filters"
                      element={<div className="page-body"><Filters /></div>}
                    />
                    <Route
                      path="/profile"
                      element={<div className="page-body"><Profile /></div>}
                    />
                  </Routes>
                </div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
