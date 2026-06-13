import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useMe, useLogout } from '../hooks/useAuth';
import { authApi } from '../api/auth';

const TIMEZONES = [
  'Europe/Rome', 'Europe/London', 'Europe/Berlin', 'Europe/Paris',
  'Europe/Madrid', 'Europe/Lisbon', 'America/New_York', 'America/Los_Angeles',
  'Asia/Tokyo', 'Australia/Sydney',
];

export function Profile() {
  const { data: user } = useMe();
  const qc = useQueryClient();
  const logout = useLogout();

  const [timezone, setTimezone] = useState(user?.timezone ?? 'Europe/Rome');
  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [profileMsg, setProfileMsg] = useState('');
  const [profileErr, setProfileErr] = useState('');
  const [pwMsg, setPwMsg] = useState('');
  const [pwErr, setPwErr] = useState('');
  const [showDelete, setShowDelete] = useState(false);

  const updateProfile = useMutation({
    mutationFn: (body: Parameters<typeof authApi.updateMe>[0]) =>
      authApi.updateMe(body).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['me'] });
      setProfileMsg('Timezone aggiornato!');
      setProfileErr('');
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setProfileErr(msg || 'Errore aggiornamento profilo');
      setProfileMsg('');
    },
  });

  const updatePw = useMutation({
    mutationFn: (body: Parameters<typeof authApi.updateMe>[0]) =>
      authApi.updateMe(body).then((r) => r.data),
    onSuccess: () => {
      setPwMsg('Password aggiornata!');
      setPwErr('');
      setCurrentPw(''); setNewPw(''); setConfirmPw('');
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setPwErr(msg || 'Errore aggiornamento password');
      setPwMsg('');
    },
  });

  const deleteAccount = useMutation({
    mutationFn: () => authApi.deleteMe(),
    onSuccess: () => logout(),
  });

  async function saveProfile(e: React.FormEvent) {
    e.preventDefault();
    await updateProfile.mutateAsync({ timezone });
  }

  async function changePassword(e: React.FormEvent) {
    e.preventDefault();
    if (newPw !== confirmPw) { setPwErr('Le password non coincidono'); return; }
    await updatePw.mutateAsync({ current_password: currentPw, new_password: newPw });
  }

  if (!user) return <div className="spinner" />;

  return (
    <div style={{ maxWidth: 600 }}>
      <h2 className="section-title">Profilo</h2>

      <div className="card" style={{ padding: 24, marginBottom: 20 }}>
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 18, fontWeight: 700 }}>{user.email}</div>
          <div style={{ fontSize: 13, color: 'var(--muted)', marginTop: 4 }}>
            Membro dal {new Date(user.created_at).toLocaleDateString('it-IT')}
            {' · '}{user.filter_count} filtri · {user.device_count} dispositivi
          </div>
          <div style={{ marginTop: 8 }}>
            {user.is_verified ? (
              <span className="badge badge-green">✓ Email verificata</span>
            ) : (
              <span className="badge badge-yellow">⚠ Email non verificata</span>
            )}
          </div>
        </div>

        <form onSubmit={saveProfile} className="form-stack">
          <div className="form-group">
            <label>Timezone</label>
            <select value={timezone} onChange={(e) => setTimezone(e.target.value)}>
              {TIMEZONES.map((tz) => <option key={tz} value={tz}>{tz}</option>)}
            </select>
          </div>
          {profileErr && <p className="error-msg">{profileErr}</p>}
          {profileMsg && <p className="success-msg">{profileMsg}</p>}
          <div>
            <button className="btn btn-primary" type="submit" disabled={updateProfile.isPending}>
              {updateProfile.isPending ? 'Salvataggio...' : 'Salva'}
            </button>
          </div>
        </form>
      </div>

      <div className="card" style={{ padding: 24, marginBottom: 20 }}>
        <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 16 }}>Cambia password</h3>
        <form onSubmit={changePassword} className="form-stack">
          <div className="form-group">
            <label>Password attuale</label>
            <input type="password" value={currentPw} onChange={(e) => setCurrentPw(e.target.value)} required />
          </div>
          <div className="form-group">
            <label>Nuova password</label>
            <input type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} required minLength={8} />
          </div>
          <div className="form-group">
            <label>Conferma nuova password</label>
            <input type="password" value={confirmPw} onChange={(e) => setConfirmPw(e.target.value)} required minLength={8} />
          </div>
          {pwErr && <p className="error-msg">{pwErr}</p>}
          {pwMsg && <p className="success-msg">{pwMsg}</p>}
          <div>
            <button className="btn btn-primary" type="submit" disabled={updatePw.isPending}>
              {updatePw.isPending ? 'Aggiornamento...' : 'Aggiorna password'}
            </button>
          </div>
        </form>
      </div>

      <div className="card" style={{ padding: 24, borderColor: '#fca5a5' }}>
        <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 8, color: 'var(--danger)' }}>Zona pericolosa</h3>
        <p className="text-sm text-muted" style={{ marginBottom: 12 }}>
          L'eliminazione dell'account è permanente e non può essere annullata.
        </p>
        {!showDelete ? (
          <button className="btn btn-danger btn-sm" onClick={() => setShowDelete(true)}>
            Elimina account
          </button>
        ) : (
          <div>
            <p className="text-sm" style={{ marginBottom: 12, color: 'var(--danger)' }}>
              Sei sicuro? Questa azione non può essere annullata.
            </p>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-danger btn-sm" onClick={() => deleteAccount.mutate()} disabled={deleteAccount.isPending}>
                {deleteAccount.isPending ? 'Eliminazione...' : 'Sì, elimina account'}
              </button>
              <button className="btn btn-ghost btn-sm" onClick={() => setShowDelete(false)}>Annulla</button>
            </div>
          </div>
        )}
      </div>

      <div className="mt-4">
        <button className="btn btn-ghost" onClick={logout}>Esci dall'account</button>
      </div>
    </div>
  );
}
