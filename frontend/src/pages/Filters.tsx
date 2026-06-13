import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { filtersApi } from '../api/filters';
import type { FilterCreate } from '../types';

const EMPTY: FilterCreate = { name: '' };

export function Filters() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<FilterCreate>(EMPTY);
  const [error, setError] = useState('');

  const { data: filters = [], isLoading } = useQuery({
    queryKey: ['filters'],
    queryFn: () => filtersApi.list().then((r) => r.data),
  });

  const create = useMutation({
    mutationFn: (body: FilterCreate) => filtersApi.create(body).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['filters'] });
      setShowForm(false);
      setForm(EMPTY);
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || 'Errore nella creazione del filtro');
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => filtersApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['filters'] }),
  });

  function set<K extends keyof FilterCreate>(key: K, val: FilterCreate[K]) {
    setForm((f) => ({ ...f, [key]: val || undefined }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    if (!form.name.trim()) { setError('Il nome è obbligatorio'); return; }
    await create.mutateAsync(form);
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h2 className="section-title" style={{ margin: 0 }}>I tuoi filtri</h2>
        <button className="btn btn-primary btn-sm" onClick={() => setShowForm(true)}>+ Nuovo filtro</button>
      </div>

      {isLoading && <div className="spinner" />}

      {!isLoading && filters.length === 0 && !showForm && (
        <div className="empty-state">
          <div className="empty-state-icon">🔔</div>
          <p>Nessun filtro salvato. Crea il primo per ricevere notifiche sugli annunci.</p>
          <button className="btn btn-primary" style={{ marginTop: 16 }} onClick={() => setShowForm(true)}>
            Crea filtro
          </button>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {filters.map((f) => (
          <div key={f.id} className="card filter-item">
            <div>
              <div className="filter-name">{f.name}</div>
              <div className="filter-details">
                {[
                  f.city && `📍 ${f.city}`,
                  f.listing_type,
                  f.min_price && `min €${f.min_price}`,
                  f.max_price && `max €${f.max_price}`,
                  f.min_surface && `${f.min_surface}m²+`,
                  f.min_rooms && `${f.min_rooms}+ locali`,
                  f.sources?.length && `fonte: ${f.sources.join(', ')}`,
                ].filter(Boolean).join(' · ') || 'Nessun vincolo'}
              </div>
            </div>
            <button
              className="btn btn-ghost btn-sm"
              style={{ color: 'var(--danger)', flexShrink: 0 }}
              onClick={() => remove.mutate(f.id)}
              disabled={remove.isPending}
            >
              Elimina
            </button>
          </div>
        ))}
      </div>

      {showForm && (
        <div className="modal-overlay" onClick={() => setShowForm(false)}>
          <div className="card modal-box" onClick={(e) => e.stopPropagation()}>
            <h3 className="modal-title">Nuovo filtro</h3>
            <form onSubmit={submit} className="form-stack">
              <div className="form-group">
                <label>Nome *</label>
                <input type="text" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} required autoFocus />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Città</label>
                  <input type="text" placeholder="es. Milano" value={form.city ?? ''} onChange={(e) => set('city', e.target.value)} />
                </div>
                <div className="form-group">
                  <label>Tipo</label>
                  <select value={form.listing_type ?? ''} onChange={(e) => set('listing_type', e.target.value)}>
                    <option value="">Tutti</option>
                    <option value="affitto">Affitto</option>
                    <option value="vendita">Vendita</option>
                  </select>
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Prezzo min (€)</label>
                  <input type="number" value={form.min_price ?? ''} onChange={(e) => set('min_price', e.target.value ? +e.target.value : null)} />
                </div>
                <div className="form-group">
                  <label>Prezzo max (€)</label>
                  <input type="number" value={form.max_price ?? ''} onChange={(e) => set('max_price', e.target.value ? +e.target.value : null)} />
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Superficie min (m²)</label>
                  <input type="number" value={form.min_surface ?? ''} onChange={(e) => set('min_surface', e.target.value ? +e.target.value : null)} />
                </div>
                <div className="form-group">
                  <label>Locali min</label>
                  <input type="number" value={form.min_rooms ?? ''} onChange={(e) => set('min_rooms', e.target.value ? +e.target.value : null)} />
                </div>
              </div>
              {error && <p className="error-msg">{error}</p>}
              <div className="modal-actions">
                <button type="button" className="btn btn-ghost" onClick={() => setShowForm(false)}>Annulla</button>
                <button type="submit" className="btn btn-primary" disabled={create.isPending}>
                  {create.isPending ? 'Salvataggio...' : 'Salva filtro'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
