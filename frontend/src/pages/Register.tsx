import { useState } from 'react';
import { Link } from 'react-router-dom';
import { authApi } from '../api/auth';

export function Register() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(''); setSuccess('');
    setLoading(true);
    try {
      const { data } = await authApi.register(email, password);
      setSuccess(data.message || 'Controlla la tua email per verificare l\'account.');
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || 'Registrazione fallita');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-center">
      <div className="card auth-box">
        <h1 className="auth-title">Registrati</h1>
        <p className="auth-sub">Crea il tuo account gratuito.</p>
        <form onSubmit={submit} className="form-stack">
          <div className="form-group">
            <label>Email</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
          </div>
          <div className="form-group">
            <label>Password <span className="text-muted">(min. 8 caratteri)</span></label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
            />
          </div>
          {error && <p className="error-msg">{error}</p>}
          {success && <p className="success-msg">{success}</p>}
          {!success && (
            <button className="btn btn-primary btn-full" type="submit" disabled={loading}>
              {loading ? 'Registrazione...' : 'Crea account'}
            </button>
          )}
          <p className="text-sm text-muted" style={{ textAlign: 'center' }}>
            Hai già un account? <Link to="/login">Accedi</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
