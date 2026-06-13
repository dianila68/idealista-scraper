import { useQuery } from '@tanstack/react-query';
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import { listingsApi } from '../api/listings';
import 'leaflet/dist/leaflet.css';

function priceColor(price: number | null): string {
  if (!price) return '#94a3b8';
  if (price < 800) return '#16a34a';
  if (price < 1500) return '#d97706';
  return '#dc2626';
}

function fmt(n: number | null) {
  if (!n) return '—';
  return new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(n);
}

export function MapView() {
  const { data, isLoading } = useQuery({
    queryKey: ['map'],
    queryFn: () => listingsApi.map().then((r) => r.data.listings),
  });

  const listings = data ?? [];

  return (
    <div style={{ position: 'relative' }}>
      {isLoading && (
        <div style={{ position: 'absolute', top: 16, left: '50%', transform: 'translateX(-50%)', zIndex: 1000, background: '#fff', padding: '8px 16px', borderRadius: 8, boxShadow: '0 2px 8px rgba(0,0,0,.15)' }}>
          Caricamento mappa...
        </div>
      )}
      <MapContainer
        center={[42.0, 12.0]}
        zoom={6}
        className="map-container"
        style={{ height: 'calc(100vh - 56px)' }}
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://openstreetmap.org">OpenStreetMap</a>'
        />
        {listings.map((item) => {
          const isApprox = item.location_precision !== 'street';
          const color = priceColor(item.price);
          return (
            <CircleMarker
              key={item.id}
              center={[item.lat, item.lng]}
              radius={8}
              pathOptions={{
                color,
                weight: 2,
                fillColor: isApprox ? 'transparent' : color,
                fillOpacity: isApprox ? 0 : 0.85,
              }}
            >
              <Popup>
                <strong>{item.title}</strong><br />
                <span style={{ color: '#2563eb', fontWeight: 700 }}>{fmt(item.price)}</span><br />
                {item.zone && <>{item.zone}, </>}{item.city}<br />
                {isApprox && <em style={{ fontSize: 12 }}>Posizione approssimativa</em>}<br />
                <a href={item.url} target="_blank" rel="noopener noreferrer">Vedi annuncio →</a>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>
      <div style={{ position: 'absolute', bottom: 32, right: 16, zIndex: 1000, background: '#fff', padding: '12px 16px', borderRadius: 8, boxShadow: '0 2px 8px rgba(0,0,0,.15)', fontSize: 12 }}>
        <div style={{ fontWeight: 600, marginBottom: 6 }}>Legenda prezzi</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ width: 12, height: 12, borderRadius: '50%', background: '#16a34a', display: 'inline-block' }} />
            &lt; 800 €
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ width: 12, height: 12, borderRadius: '50%', background: '#d97706', display: 'inline-block' }} />
            800–1500 €
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ width: 12, height: 12, borderRadius: '50%', background: '#dc2626', display: 'inline-block' }} />
            &gt; 1500 €
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ width: 12, height: 12, borderRadius: '50%', border: '2px solid #94a3b8', display: 'inline-block' }} />
            Posizione approx.
          </div>
        </div>
        <div style={{ marginTop: 8, color: '#64748b' }}>{listings.length} annunci sulla mappa</div>
      </div>
    </div>
  );
}
