import { useState } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { listingsApi, type ListingParams } from '../api/listings';
import { ListingCard } from '../components/ListingCard';

const SOURCES = ['idealista', 'immobiliare', 'subito'];
const TYPES = ['affitto', 'vendita'];

export function Listings() {
  const [params, setParams] = useState<ListingParams>({ limit: 24 });
  const [draft, setDraft] = useState<ListingParams>({ limit: 24 });

  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading } = useInfiniteQuery({
    queryKey: ['listings', params],
    queryFn: ({ pageParam }) =>
      listingsApi.list({ ...params, cursor: pageParam as string | undefined }).then((r) => r.data),
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    initialPageParam: undefined as string | undefined,
  });

  const items = data?.pages.flatMap((p) => p.items) ?? [];

  function applyFilters(e: React.FormEvent) {
    e.preventDefault();
    setParams({ ...draft, limit: 24 });
  }

  function reset() {
    const clean = { limit: 24 };
    setDraft(clean);
    setParams(clean);
  }

  return (
    <div>
      <form onSubmit={applyFilters}>
        <div className="filters-bar">
          <div className="form-group">
            <label>Città</label>
            <input
              type="text"
              placeholder="es. Milano"
              value={draft.city ?? ''}
              onChange={(e) => setDraft((d) => ({ ...d, city: e.target.value || undefined }))}
            />
          </div>
          <div className="form-group">
            <label>Tipo</label>
            <select
              value={draft.listing_type ?? ''}
              onChange={(e) => setDraft((d) => ({ ...d, listing_type: e.target.value || undefined }))}
            >
              <option value="">Tutti</option>
              {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>Fonte</label>
            <select
              value={draft.source ?? ''}
              onChange={(e) => setDraft((d) => ({ ...d, source: e.target.value || undefined }))}
            >
              <option value="">Tutte</option>
              {SOURCES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>Prezzo min (€)</label>
            <input
              type="number"
              placeholder="0"
              value={draft.min_price ?? ''}
              onChange={(e) => setDraft((d) => ({ ...d, min_price: e.target.value ? +e.target.value : undefined }))}
            />
          </div>
          <div className="form-group">
            <label>Prezzo max (€)</label>
            <input
              type="number"
              placeholder="illimitato"
              value={draft.max_price ?? ''}
              onChange={(e) => setDraft((d) => ({ ...d, max_price: e.target.value ? +e.target.value : undefined }))}
            />
          </div>
          <div className="form-group">
            <label>Superficie min (m²)</label>
            <input
              type="number"
              placeholder="0"
              value={draft.min_surface ?? ''}
              onChange={(e) => setDraft((d) => ({ ...d, min_surface: e.target.value ? +e.target.value : undefined }))}
            />
          </div>
          <div className="form-group">
            <label>Locali min</label>
            <input
              type="number"
              placeholder="1"
              value={draft.min_rooms ?? ''}
              onChange={(e) => setDraft((d) => ({ ...d, min_rooms: e.target.value ? +e.target.value : undefined }))}
            />
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
            <button className="btn btn-primary" type="submit">Filtra</button>
            <button className="btn btn-ghost" type="button" onClick={reset}>Reset</button>
          </div>
        </div>
      </form>

      {isLoading && <div className="spinner" />}

      {!isLoading && items.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-icon">🔍</div>
          <p>Nessun annuncio trovato con questi filtri.</p>
        </div>
      )}

      <div className="listing-grid">
        {items.map((listing) => <ListingCard key={listing.id} listing={listing} />)}
      </div>

      {hasNextPage && (
        <div className="load-more">
          <button
            className="btn btn-ghost"
            onClick={() => fetchNextPage()}
            disabled={isFetchingNextPage}
          >
            {isFetchingNextPage ? 'Caricamento...' : 'Carica altri'}
          </button>
        </div>
      )}
    </div>
  );
}
