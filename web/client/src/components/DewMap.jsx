import { MapContainer, TileLayer, Marker, Popup, Tooltip, useMap } from 'react-leaflet';
import L from 'leaflet';
import { useEffect, useRef } from 'react';
import 'leaflet/dist/leaflet.css';

import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

const DEFAULT_CENTER = [39.8283, -98.5795];
const DEFAULT_ZOOM = 4;

// ensure default marker icons load inside bundlers like Vite
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

function formatLocalTime(timestamp, timeZone) {
  try {
    const formatter = new Intl.DateTimeFormat('en-US', {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: 'numeric',
      timeZone: timeZone || 'UTC',
    });
    return formatter.format(new Date(timestamp));
  } catch {
    return timestamp;
  }
}

export function DewMap({ finds, activeFindId }) {
  return (
    <MapContainer className="map" center={DEFAULT_CENTER} zoom={DEFAULT_ZOOM} scrollWheelZoom>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
      />
      <DewMapMarkers finds={finds} activeFindId={activeFindId} />
    </MapContainer>
  );
}

function DewMapMarkers({ finds, activeFindId }) {
  const map = useMap();
  const markerRefs = useRef({});

  useEffect(() => {
    if (!activeFindId) return;
    const marker = markerRefs.current[activeFindId];
    if (!marker) return;
    const latLng = marker.getLatLng();
    const targetZoom = Math.max(map.getZoom(), 7);
    map.flyTo(latLng, targetZoom, { duration: 0.75 });
    marker.openPopup();
  }, [activeFindId, map, finds]);

  return finds.map((find) => (
    <Marker
      key={find.id}
      position={[find.latitude, find.longitude]}
      ref={(ref) => {
        if (ref) {
          markerRefs.current[find.id] = ref;
        }
      }}
    >
      <Tooltip>{`${find.flavor} (${find.size})`}</Tooltip>
      <Popup>
        <div className="popup">
          <p className="popup__heading">
            <strong>{find.flavor}</strong> · {find.size}
          </p>
          <p>{find.locationName}</p>
          <p className="popup__meta">{find.address}</p>
          <p className="popup__meta">
            Logged: {formatLocalTime(find.createdAt, find.timeZone)} ({find.timeZone || 'UTC'})
          </p>
          {find.imageUrl && <img src={find.imageUrl} alt={`${find.flavor} at ${find.locationName}`} loading="lazy" />}
        </div>
      </Popup>
    </Marker>
  ));
}
