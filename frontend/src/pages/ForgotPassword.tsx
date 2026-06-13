import { useState } from 'react';
import { Link } from 'react-router-dom';
import { authApi } from '../api/auth';

export function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState('');

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await authApi.forgotPassword(email);
      setDone(true);
    } catch {
      setError('Si è verificato un errore. Riprova.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-center">
      <div className="card auth-box">
        <h1 className="auth-title">Reset password</h1>
        <p className="auth-sub">Inserisci la tua email per ricevere il link di reset.</p>
        {done ? (
          <>
            <p className="success-msg">
              Se l'email esiste, riceverai un link di reset a breve.
            </p>
            <div style={{ marginTop: 16 }}>
              <Link to="/login" className="btn btn-ghost btn-full">Torna al login</Link>
            </div>
          </>
        ) : (
          <form onSubmit={submit} className="form-stack">
            <div className="form-group">
              <label>Email</label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
            </div>
            {error && <p className="error-msg">{error}</p>}
            <button className="btn btn-primary btn-full" type="submit" disabled={loading}>
              {loading ? 'Invio...' : 'Invia link di reset'}
            </button>
            <p className="text-sm text-muted" style={{ textAlign: 'center' }}>
              <Link to="/login">Torna al login</Link>
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
