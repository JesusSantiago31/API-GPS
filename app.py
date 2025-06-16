from flask import Flask, render_template, request, jsonify
import requests
from math import radians, sin, cos, sqrt, atan2

app = Flask(__name__)

ORS_API_KEY = '5b3ce3597851110001cf624890499254530e4be7af8b1db44545832a'  # Cambia a tu key
ORS_BASE_URL = 'https://api.openrouteservice.org/v2/directions'

FUEL_CONSUMPTION = 0.08  # litros por km
DEFAULT_MAX_DISTANCE_LIMIT = 6000000  # 6,000 km

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/calculate_route', methods=['POST'])
def calculate_route():
    try:
        data = request.get_json()
        start = data['start']  # [lon, lat]
        end = data['end']      # [lon, lat]
        max_distance_limit = data.get('max_distance', DEFAULT_MAX_DISTANCE_LIMIT)
        max_duration_limit = data.get('max_duration')  # en minutos
        fuel_type = data.get('fuel_type', 'magna')  # por defecto magna
        max_price = data.get('max_price')  # en pesos, puede ser None

        if not isinstance(max_distance_limit, (int, float)) or max_distance_limit <= 0:
            max_distance_limit = DEFAULT_MAX_DISTANCE_LIMIT

        if not is_within_distance_limit(start, end, max_distance_limit):
            return jsonify({
                'error': f'La distancia entre los puntos es demasiado grande (más de {max_distance_limit/1000:.0f} km).'
            }), 400

        driving_route = None
        walking_route = None
        fuel_used = 0
        fuel_price_per_liter = 20 if fuel_type == 'magna' else 25

        try:
            driving_route = get_route(start, end, profile='driving-car')
            distance_km = driving_route['distance'] / 1000
            fuel_used = distance_km * FUEL_CONSUMPTION
            total_price = fuel_used * fuel_price_per_liter

            # Validar duración máxima
            if max_duration_limit is not None:
                duration_min = driving_route['duration'] / 60
                if duration_min > max_duration_limit:
                    return jsonify({
                        'error': f'La duración estimada en auto ({duration_min:.1f} min) supera el tiempo máximo permitido ({max_duration_limit} min).'
                    }), 400

            # Validar precio máximo
            if max_price is not None:
                if total_price > float(max_price):
                    return jsonify({
                        'error': f'El costo estimado del viaje en {fuel_type.capitalize()} (${total_price:.2f}) excede el precio máximo permitido (${max_price}).'
                    }), 400

        except Exception as e:
            driving_route = None

        try:
            walking_route = get_route(start, end, profile='foot-walking')
            if max_duration_limit is not None:
                duration_min = walking_route['duration'] / 60
                if duration_min > max_duration_limit:
                    walking_route = None
        except Exception:
            walking_route = None

        if not driving_route and not walking_route:
            return jsonify({
                'error': 'No hay ruta disponible dentro de las restricciones indicadas.'
            }), 404

        return jsonify({
            'driving_geometry': driving_route['geometry'] if driving_route else None,
            'walking_geometry': walking_route['geometry'] if walking_route else None,
            'distance': driving_route['distance'] if driving_route else walking_route['distance'],
            'duration': driving_route['duration'] if driving_route else walking_route['duration'],
            'fuel_used': fuel_used,
            'start': start,
            'end': end,
            'has_driving_route': driving_route is not None,
            'has_walking_route': walking_route is not None
        })

    except Exception as e:
        return jsonify({'error': f"Error al procesar la solicitud: {str(e)}"}), 500


def get_route(start, end, profile='driving-car'):
    headers = {
        'Authorization': ORS_API_KEY,
        'Content-Type': 'application/json; charset=utf-8'
    }
    body = {
        "coordinates": [start, end],
        "instructions": False,
        "geometry": True
    }
    url = f"{ORS_BASE_URL}/{profile}"
    response = requests.post(url, headers=headers, json=body)

    if response.status_code == 200:
        data = response.json()
        geometry = data['routes'][0]['geometry']
        distance = data['routes'][0]['summary']['distance']
        duration = data['routes'][0]['summary']['duration']
        return {
            'geometry': geometry,
            'distance': distance,
            'duration': duration
        }
    else:
        error_data = response.json()
        error_code = error_data.get('error', {}).get('code')
        if error_code == 2010:
            transport_type = 'auto' if profile == 'driving-car' else 'pie'
            raise Exception(f"No hay ruta disponible para {transport_type}")
        elif error_code == 2004:
            raise Exception(f"Distancia demasiado grande para {profile}")
        else:
            raise Exception(f"Error de ORS: {response.text}")

def is_within_distance_limit(start, end, max_distance_limit):
    lat1, lon1 = radians(start[1]), radians(start[0])
    lat2, lon2 = radians(end[1]), radians(end[0])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    distance = 6371000 * c
    return distance <= max_distance_limit

if __name__ == '__main__':
    app.run(debug=True)
