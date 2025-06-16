// Inicializar mapa centrado en CDMX
const map = L.map('map').setView([19.4326, -99.1332], 13);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution:
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
}).addTo(map);

let startMarker = null;
let endMarker = null;
let routeLayer = null;
let currentMode = 'start';
let precioGasolina = 24;

const setStartBtn = document.getElementById('set-start');
const setEndBtn = document.getElementById('set-end');
const clearBtn = document.getElementById('clear-markers');
const distanceEl = document.getElementById('distance');
const durationEl = document.getElementById('duration');
const fuelEl = document.getElementById('fuel');
const fuelPrice = document.getElementById('fuel-price');
const instructionsEl = document.getElementById('instructions');
const loadingOverlay = document.getElementById('loading-overlay');

setStartBtn.addEventListener('click', () => {
  currentMode = 'start';
  setStartBtn.classList.add('active');
  setEndBtn.classList.remove('active');
});

setEndBtn.addEventListener('click', () => {
  currentMode = 'end';
  setEndBtn.classList.add('active');
  setStartBtn.classList.remove('active');
});

clearBtn.addEventListener('click', () => {
  clearMarkers();
});

map.on('click', async (e) => {
  const coords = [e.latlng.lng, e.latlng.lat];

  if (currentMode === 'start') {
    setStartMarker(e.latlng);
  } else {
    setEndMarker(e.latlng);
  }

  if (startMarker && endMarker) {
    await calculateRoute();
  }
});

function setStartMarker(latlng) {
  if (startMarker) {
    map.removeLayer(startMarker);
  }
  startMarker = L.marker(latlng, {
    draggable: true,
    icon: L.divIcon({
      className: 'marker-icon start-marker',
      html: '🟢',
      iconSize: [24, 24],
    }),
  })
    .addTo(map)
    .bindPopup('Origen')
    .on('dragend', async function () {
      await calculateRoute();
    });
}

function setEndMarker(latlng) {
  if (endMarker) {
    map.removeLayer(endMarker);
  }
  endMarker = L.marker(latlng, {
    draggable: true,
    icon: L.divIcon({
      className: 'marker-icon end-marker',
      html: '🔴',
      iconSize: [24, 24],
    }),
  })
    .addTo(map)
    .bindPopup('Destino')
    .on('dragend', async function () {
      await calculateRoute();
    });
}

function clearMarkers() {
  if (startMarker) {
    map.removeLayer(startMarker);
    startMarker = null;
  }
  if (endMarker) {
    map.removeLayer(endMarker);
    endMarker = null;
  }
  if (routeLayer) {
    map.removeLayer(routeLayer);
    routeLayer = null;
  }
  distanceEl.textContent = '-';
  durationEl.textContent = '-';
  fuelEl.textContent = '-';
  fuelPrice.textContent = '-';
  instructionsEl.innerHTML = '';
}

// ... (tu código original arriba, sin cambios)
async function calculateRoute() {
  if (!startMarker || !endMarker) return;

  loadingOverlay.style.display = 'flex';

  const startCoords = [startMarker.getLatLng().lng, startMarker.getLatLng().lat];
  const endCoords = [endMarker.getLatLng().lng, endMarker.getLatLng().lat];
  const routeType = document.querySelector('input[name="route-type"]:checked').value;

  const maxDistanceKm = Number(document.getElementById('max-distance-input').value);
  const maxDistanceMeters = maxDistanceKm * 1000;
  const maxDurationMinutes = Number(document.getElementById('max-duration-input').value);

  // NUEVO: Obtener tipo de gasolina y su precio
  const gasolineSelect = document.getElementById('gasoline-type');
  const selectedOption = gasolineSelect.options[gasolineSelect.selectedIndex];
  const tipoGasolina = selectedOption.value;
  const precioGasolina = parseFloat(selectedOption.getAttribute('data-precio'));

  // NUEVO: Obtener precio máximo permitido
  const precioMaximoRuta = Number(document.getElementById('max-price-input').value);

  try {
    const response = await axios.post('/calculate_route', {
      start: startCoords,
      end: endCoords,
      max_distance: maxDistanceMeters,
      max_duration: maxDurationMinutes,
      tipo_gasolina: tipoGasolina,
      precio_maximo: precioMaximoRuta,
    });

    const route = response.data;

    const hasRoute =
      routeType === 'driving' ? route.has_driving_route : route.has_walking_route;

    if (!hasRoute) {
      throw new Error(`No hay ruta disponible para ${routeType === 'driving' ? 'auto' : 'pie'}`);
    }

    const routeDurationMinutes = route.duration / 60;
    if (maxDurationMinutes && routeDurationMinutes > maxDurationMinutes) {
      throw new Error(
        `La ruta supera el tiempo máximo permitido (${maxDurationMinutes} min). Duración estimada: ${routeDurationMinutes.toFixed(2)} min`
      );
    }

    const geometry = routeType === 'driving' ? route.driving_geometry : route.walking_geometry;

    distanceEl.textContent = `${(route.distance / 1000).toFixed(2)} km`;

    let durationMinutes = Math.ceil(route.duration / 60);
    if (routeType === 'walking') durationMinutes *= 2;
    durationEl.textContent = `${durationMinutes} minutos`;

    if (routeType === 'driving') {
      fuelEl.textContent = `${route.fuel_used.toFixed(2)} litros`;
      const totalFuelPrice = route.fuel_used * precioGasolina;
      fuelPrice.textContent = `$ ${totalFuelPrice.toFixed(2)} pesos`;

      // NUEVO: Verificar si el precio total de gasolina excede el máximo
      if (precioMaximoRuta && totalFuelPrice > precioMaximoRuta) {
        throw new Error(
          `El costo de gasolina ($${totalFuelPrice.toFixed(2)}) excede el precio máximo permitido ($${precioMaximoRuta.toFixed(2)}).`
        );
      }
    } else {
      fuelEl.textContent = 'N/A';
      fuelPrice.textContent = '-';
    }

    const coordinates = decodePolyline(geometry);
    const bounds = L.latLngBounds(coordinates.map((c) => [c[1], c[0]]));
    map.fitBounds(bounds, { padding: [50, 50] });

    if (routeLayer) map.removeLayer(routeLayer);

    routeLayer = L.polyline(coordinates.map((c) => [c[1], c[0]]), {
      color: routeType === 'driving' ? '#4285f4' : '#34a853',
      weight: 6,
      opacity: 0.8,
      lineJoin: 'round',
    }).addTo(map);
  } catch (error) {
    console.error(error);
    if (routeLayer) {
      map.removeLayer(routeLayer);
      routeLayer = null;
    }
    distanceEl.textContent = '-';
    durationEl.textContent = '-';
    fuelEl.textContent = '-';
    fuelPrice.textContent = '-';

    alert('Error al calcular la ruta: ' + (error.response?.data?.error || error.message));
  } finally {
    loadingOverlay.style.display = 'none';
  }
}

// ... (el resto de funciones sin cambios)


function decodePolyline(encoded) {
  let index = 0,
    len = encoded.length;
  let lat = 0,
    lng = 0;
  const array = [];

  while (index < len) {
    let b,
      shift = 0,
      result = 0;

    do {
      b = encoded.charCodeAt(index++) - 63;
      result |= (b & 0x1f) << shift;
      shift += 5;
    } while (b >= 0x20);

    let dlat = (result & 1) ? ~(result >> 1) : result >> 1;
    lat += dlat;

    shift = 0;
    result = 0;

    do {
      b = encoded.charCodeAt(index++) - 63;
      result |= (b & 0x1f) << shift;
      shift += 5;
    } while (b >= 0x20);

    let dlng = (result & 1) ? ~(result >> 1) : result >> 1;
    lng += dlng;

    array.push([lng * 1e-5, lat * 1e-5]);
  }

  return array;
}

// NUEVO: actualizar ruta automáticamente al cambiar tipo de ruta (sin perder marcadores)
document.querySelectorAll('input[name="route-type"]').forEach((input) => {
  input.addEventListener('change', async () => {
    if (startMarker && endMarker) {
      await calculateRoute();
    }
  });
});
