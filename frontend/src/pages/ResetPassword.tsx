import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { authApi } from '../api/auth';

export function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState('');

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirm) { setError('Le password non coincidono.'); return; }
    setError('');
    setLoading(true);
    try {
      await authApi.resetPassword(token, password);
      setDone(true);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || 'Token non valido o scaduto.');
    } finally {
      setLoading(false);
    }
  }

  if (!token) return (
    <div className="page-center">
      <div className="card auth-box">
        <p className="error-msg">Link non valido. Richiedi un nuovo link di reset.</p>
        <div className="mt-4"><Link to="/forgot-password" className="btn btn-primary btn-full">Reset password</Link></div>
      </div>
    </div>
  );

  return (
    <div className="page-center">
      <div className="card auth-box">
        <h1 className="auth-title">Nuova password</h1>
        <p className="auth-sub">Scegli una nuova password per il tuo account.</p>
        {done ? (
          <>
            <p className="success-msg">Password aggiornata con successo!</p>
            <div className="mt-4"><Link to="/login" className="btn btn-primary btn-full">Accedi</Link></div>
          </>
        ) : (
          <form onSubmit={submit} className="form-stack">
            <div className="form-group">
              <label>Nuova password</label>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} autoFocus />
            </div>
            <div className="form-group">
              <label>Conferma password</label>
              <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required minLength={8} />
            </div>
            {error && <p className="error-msg">{error}</p>}
            <button className="btn btn-primary btn-full" type="submit" disabled={loading}>
              {loading ? 'Aggiornamento...' : 'Aggiorna password'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
