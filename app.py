from flask import Flask, render_template, request, jsonify
import requests
from math import radians, sin, cos, sqrt, atan2

app = Flask(__name__)

# Configuración de OpenRouteService
ORS_API_KEY = '5b3ce3597851110001cf624890499254530e4be7af8b1db44545832a'
ORS_BASE_URL = 'https://api.openrouteservice.org/v2/directions'
ORS_GEOCODE_URL = 'https://api.openrouteservice.org/geocode/search'

# Consumo promedio de gasolina
FUEL_CONSUMPTION = {
    "car": 0.16,
    "moto": 0.08
}
MAX_DISTANCE_LIMIT = 6000000  # 6,000 km en metros

# Precios por litro de combustible (MXN)
FUEL_PRICES = {
    "regular": 22.50,
    "premium": 24.50,
    "diesel": 23.00
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/geocode', methods=['POST'])
def geocode():
    """Geocodifica una dirección a coordenadas"""
    try:
        data = request.get_json()
        address = data['address']
        
        headers = {
            'Authorization': ORS_API_KEY,
            'Content-Type': 'application/json'
        }
        
        params = {
            'text': address,
            'size': 1
        }
        
        response = requests.get(ORS_GEOCODE_URL, headers=headers, params=params)
        if response.status_code != 200:
            raise Exception(f"Error en geocodificación: {response.json().get('error', 'Dirección no encontrada')}")
        
        data = response.json()
        if not data['features']:
            raise Exception("Dirección no encontrada")
        
        coordinates = data['features'][0]['geometry']['coordinates']
        return jsonify({
            'coordinates': coordinates,
            'address': data['features'][0]['properties']['label']
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/calculate_route', methods=['POST'])
def calculate_route():
    try:
        data = request.get_json()
        
        # Validar que se proporcionaron direcciones
        if 'start_text' not in data or not data['start_text'] or 'end_text' not in data or not data['end_text']:
            return jsonify({'error': 'Debes proporcionar direcciones de origen y destino válidas'}), 400
            
        # Geocodificar direcciones
        start = geocode_address(data['start_text'])
        end = geocode_address(data['end_text'])
            
        fuel_type = data.get('fuel_type', 'regular')
        speed_kmh = float(data.get('speed', 60))
        vehicle_type = data.get('vehicle_type', 'car')

        # Validaciones
        if fuel_type not in FUEL_PRICES:
            return jsonify({'error': 'Tipo de gasolina no válido'}), 400
        if speed_kmh <= 0 or speed_kmh > 120:
            return jsonify({'error': 'Velocidad debe ser entre 1 y 120 km/h'}), 400
        if not is_within_distance_limit(start, end):
            return jsonify({'error': 'Distancia máxima excedida (6,000 km)'}), 400
        if vehicle_type not in FUEL_CONSUMPTION:
            return jsonify({'error': 'Tipo de vehículo no válido'}), 400

        # Obtener ruta
        driving_route = get_route(start, end, 'driving-car')

        # Calcular métricas
        distance_km = driving_route['distance'] / 1000
        fuel_used = distance_km * FUEL_CONSUMPTION[vehicle_type]
        fuel_cost = fuel_used * FUEL_PRICES[fuel_type]
        duration_h = distance_km / speed_kmh
        duration = duration_h * 3600  # Convertir a segundos

        return jsonify({
            'geometry': driving_route['geometry'],
            'distance': distance_km,
            'duration': duration,
            'fuel_used': fuel_used,
            'fuel_cost': fuel_cost,
            'fuel_type': fuel_type,
            'speed': speed_kmh,
            'vehicle_type': vehicle_type,
            'start_coords': start,
            'end_coords': end,
            'start_address': data['start_text'],
            'end_address': data['end_text']
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

def geocode_address(address):
    """Geocodifica una dirección a coordenadas usando ORS"""
    headers = {
        'Authorization': ORS_API_KEY,
        'Content-Type': 'application/json'
    }
    
    params = {
        'text': address,
        'size': 1
    }
    
    response = requests.get(ORS_GEOCODE_URL, headers=headers, params=params)
    if response.status_code != 200:
        raise Exception(f"Error en geocodificación: {response.json().get('error', 'Dirección no encontrada')}")
    
    data = response.json()
    if not data['features']:
        raise Exception("Dirección no encontrada")
    
    return data['features'][0]['geometry']['coordinates']

def get_route(start, end, profile):
    """Obtiene una ruta desde la API de OpenRouteService"""
    headers = {
        'Authorization': ORS_API_KEY,
        'Content-Type': 'application/json'
    }
    body = {"coordinates": [start, end], "instructions": "false"}
    
    response = requests.post(f"{ORS_BASE_URL}/{profile}", headers=headers, json=body)
    if response.status_code != 200:
        raise Exception(f"Error ORS: {response.json().get('error', 'Sin ruta disponible')}")
    
    data = response.json()
    return {
        'geometry': data['routes'][0]['geometry'],
        'distance': data['routes'][0]['summary']['distance'],
        'duration': data['routes'][0]['summary']['duration']
    }

def is_within_distance_limit(start, end):
    """Verifica si la distancia está dentro del límite usando Haversine"""
    lat1, lon1 = radians(start[1]), radians(start[0])
    lat2, lon2 = radians(end[1]), radians(end[0])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    distance = 6371000 * 2 * atan2(sqrt(a), sqrt(1-a))  # Metros
    return distance <= MAX_DISTANCE_LIMIT

if __name__ == '__main__':
    app.run(debug=True)