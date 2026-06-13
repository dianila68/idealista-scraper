import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useLogin } from '../hooks/useAuth';

export function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();
  const login = useLogin();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await login.mutateAsync({ email, password });
      navigate('/listings');
    } catch {
      // error shown below
    }
  }

  const errMsg = (login.error as { response?: { data?: { detail?: string } } })
    ?.response?.data?.detail ?? (login.isError ? 'Accesso fallito' : null);

  return (
    <div className="page-center">
      <div className="card auth-box">
        <h1 className="auth-title">Accedi</h1>
        <p className="auth-sub">Bentornato! Inserisci le tue credenziali.</p>
        <form onSubmit={submit} className="form-stack">
          <div className="form-group">
            <label>Email</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
          </div>
          <div className="form-group">
            <label>Password</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </div>
          {errMsg && <p className="error-msg">{errMsg}</p>}
          <button className="btn btn-primary btn-full" type="submit" disabled={login.isPending}>
            {login.isPending ? 'Accesso...' : 'Accedi'}
          </button>
          <p className="text-sm text-muted" style={{ textAlign: 'center' }}>
            Non hai un account? <Link to="/register">Registrati</Link>
          </p>
          <p className="text-sm" style={{ textAlign: 'center' }}>
            <Link to="/forgot-password">Password dimenticata?</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
