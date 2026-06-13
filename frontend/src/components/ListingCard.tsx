import type { Listing } from '../types';

function fmt(n: number | null) {
  if (n == null) return '—';
  return new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(n);
}

export function ListingCard({ listing }: { listing: Listing }) {
  return (
    <a href={listing.url} target="_blank" rel="noopener noreferrer" style={{ textDecoration: 'none' }}>
      <div className="card listing-card">
        {listing.image_urls.length > 0 ? (
          <img className="listing-img" src={listing.image_urls[0]} alt={listing.title} loading="lazy" />
        ) : (
          <div className="listing-img-placeholder">🏠</div>
        )}
        <div className="listing-body">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="listing-price">{fmt(listing.price)}</span>
            <span className="listing-source">{listing.source}</span>
          </div>
          <p className="listing-title">{listing.title}</p>
          <div className="listing-meta">
            {listing.city && <span className="listing-tag">📍 {listing.zone ? `${listing.zone}, ` : ''}{listing.city}</span>}
            {listing.surface_m2 && <span className="listing-tag">{listing.surface_m2} m²</span>}
            {listing.rooms && <span className="listing-tag">{listing.rooms} loc.</span>}
            {listing.floor != null && <span className="listing-tag">P.{listing.floor}</span>}
            {listing.is_furnished && <span className="listing-tag">Arredato</span>}
          </div>
        </div>
      </div>
    </a>
  );
}
