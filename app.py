from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session
import googlemaps
import google.generativeai as genai
from dotenv import load_dotenv
import os
from models import db, Hospital, Ambulance
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import requests
from datetime import datetime

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hospitals.db'

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'hospital_login'

WEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY')

# Weather alert thresholds
WEATHER_ALERTS = {
    'extreme_temp': {'min': 0, 'max': 45},  # Celsius
    'wind_speed': 20,  # m/s
    'rain': 50,  # mm
    'snow': 20,  # mm
}

@login_manager.user_loader
def load_user(user_id):
    return Hospital.query.get(int(user_id))

# Initialize Google Maps and Gemini AI
gmaps = googlemaps.Client(key=os.getenv('GOOGLE_MAPS_API_KEY'))
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-pro')

# Sample hospital data - in real app, this would come from a database
hospitals = {
    "City Hospital": {
        "beds": 45,
        "available_beds": 15,
        "oxygen_cylinders": 30,
        "location": {"lat": 28.6139, "lng": 77.2090},
        "specialties": ["Emergency Care", "ICU", "Covid Care"],
        "contact": "+91-9876543210"
    },
    "Apollo Hospital": {
        "beds": 120,
        "available_beds": 35,
        "oxygen_cylinders": 80,
        "location": {"lat": 28.6129, "lng": 77.2295},
        "specialties": ["Multi-Specialty", "Cancer Care", "Cardiac"],
        "contact": "+91-9876543211"
    },
    "Max Super Specialty": {
        "beds": 200,
        "available_beds": 50,
        "oxygen_cylinders": 100,
        "location": {"lat": 28.6271, "lng": 77.2191},
        "specialties": ["Neurology", "Orthopedics", "Pediatrics"],
        "contact": "+91-9876543212"
    },
    "Fortis Healthcare": {
        "beds": 150,
        "available_beds": 30,
        "oxygen_cylinders": 75,
        "location": {"lat": 28.6180, "lng": 77.2145},
        "specialties": ["Cardiology", "Oncology", "Emergency"],
        "contact": "+91-9876543213"
    }
}

# Sample ambulance data
ambulances = {
    "AMB-001": {
        "type": "Basic Life Support",
        "driver_name": "Rajesh Kumar",
        "contact": "+91-9876543214",
        "location": {"lat": 28.6139, "lng": 77.2090},
        "is_available": True,
        "hospital": "City Hospital"
    },
    "AMB-002": {
        "type": "Advanced Life Support",
        "driver_name": "Suresh Singh",
        "contact": "+91-9876543215",
        "location": {"lat": 28.6129, "lng": 77.2295},
        "is_available": True,
        "hospital": "Apollo Hospital"
    },
    "AMB-003": {
        "type": "Patient Transport",
        "driver_name": "Amit Sharma",
        "contact": "+91-9876543216",
        "location": {"lat": 28.6271, "lng": 77.2191},
        "is_available": True,
        "hospital": "Max Super Specialty"
    }
}

@app.route('/')
def home():
    return render_template('index.html', 
        google_maps_api_key=os.getenv('GOOGLE_MAPS_API_KEY'),
        hospitals=hospitals,
        ambulances=ambulances
    )

@app.route('/find_hospitals/<lat>/<lng>')
def find_hospitals(lat, lng):
    # Get hospitals from database
    db_hospitals = Hospital.query.all()
    hospitals_list = [hospital.to_dict() for hospital in db_hospitals]
    
    # Calculate distances and add to hospital data
    for hospital in hospitals_list:
        hospital['distance'] = calculate_distance(
            float(lat), float(lng),
            hospital['location']['lat'],
            hospital['location']['lng']
        )
    
    # Get AI recommendation with more context
    prompt = f"""Based on the user's location ({lat}, {lng}), analyze these hospitals and provide detailed recommendations.
    Hospital Data: {str(hospitals_list)}

    Please recommend the top 3 most suitable hospitals considering:
    1. Proximity (closer hospitals are preferred)
    2. Current capacity (available beds and oxygen cylinders)
    3. Emergency readiness and ICU availability
    4. Relevant specialties and facilities
    5. Hospital ratings and reviews

    For each recommended hospital, provide:
    1. Hospital Name and Distance
    2. Key Strengths (what makes this hospital particularly suitable)
    3. Current Availability:
       - Regular beds
       - ICU beds
       - Oxygen cylinders
    4. Estimated travel time
    5. Emergency services status
    6. Notable specialties
    7. Any special notes or warnings

    Format each recommendation clearly with headings and bullet points.
    If a hospital is at full capacity or has emergency alerts, please mention this prominently.
    
    Also include a brief explanation of why these specific hospitals were chosen over others."""
    
    try:
        response = model.generate_content(prompt)
        recommendation = response.text
    except Exception as e:
        recommendation = "Unable to generate recommendations at the moment. Please check the hospital list below."
    
    return jsonify({
        'hospitals': sorted(hospitals_list, key=lambda x: x['distance'])[:5],  # Top 5 nearest hospitals
        'recommendation': recommendation,
        'ambulances': [amb for amb in ambulances.values() if amb['is_available']]
    })

@app.route('/hospital_status')
def hospital_status():
    return jsonify(hospitals)

# Hospital routes
@app.route('/hospital/register', methods=['GET', 'POST'])
def hospital_register():
    if request.method == 'POST':
        try:
            # Get location data with defaults if not provided
            lat = float(request.form.get('latitude', 20.5937))
            lng = float(request.form.get('longitude', 78.9629))

            hospital = Hospital(
                name=request.form['name'],
                email=request.form['email'],
                address=request.form['address'],
                contact_number=request.form['contact'],
                total_beds=int(request.form['total_beds']),
                available_beds=int(request.form['total_beds']),
                oxygen_cylinders=int(request.form.get('oxygen_cylinders', 0)),
                icu_beds=int(request.form.get('icu_beds', 0)),
                emergency_status='available',
                location_lat=lat,
                location_lng=lng
            )
            hospital.set_password(request.form['password'])
            
            db.session.add(hospital)
            db.session.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('hospital_login'))
        except Exception as e:
            db.session.rollback()
            flash('Registration failed. Please ensure all fields are filled correctly.', 'error')
            print(f"Registration error: {str(e)}")  # For debugging
    
    return render_template('hospital/register.html')

@app.route('/hospital/login', methods=['GET', 'POST'])
def hospital_login():
    if current_user.is_authenticated:
        return redirect(url_for('hospital_dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = 'remember' in request.form

        hospital = Hospital.query.filter_by(email=email).first()
        if hospital and hospital.check_password(password):
            login_user(hospital, remember=remember)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('hospital_dashboard'))
        else:
            flash('Invalid email or password')

    return render_template('hospital/login.html')

@app.route('/hospital/logout')
@login_required
def hospital_logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/hospital/dashboard')
@login_required
def hospital_dashboard():
    return render_template('hospital/dashboard.html')

@app.route('/hospital/update', methods=['POST'])
@login_required
def update_hospital_status():
    hospital = current_user
    hospital.available_beds = request.form.get('available_beds', type=int)
    hospital.oxygen_cylinders = request.form.get('oxygen_cylinders', type=int)
    hospital.icu_beds = request.form.get('icu_beds', type=int)
    hospital.emergency_status = request.form.get('emergency_status')
    
    try:
        db.session.commit()
        return jsonify({'success': True, 'message': 'Hospital information updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/hospital/update_info', methods=['POST'])
@login_required
def update_hospital_info():
    try:
        current_user.name = request.form.get('name')
        current_user.address = request.form.get('address')
        current_user.contact_number = request.form.get('contact_number')
        current_user.emergency_contact = request.form.get('emergency_contact')
        current_user.specialties = request.form.get('specialties')
        
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/hospital/update_facilities', methods=['POST'])
@login_required
def update_facilities():
    try:
        current_user.total_beds = request.form.get('total_beds', type=int)
        current_user.available_beds = request.form.get('available_beds', type=int)
        current_user.icu_beds = request.form.get('icu_beds', type=int)
        current_user.oxygen_cylinders = request.form.get('oxygen_cylinders', type=int)
        current_user.emergency_status = request.form.get('emergency_status')
        
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

# Ambulance routes
@app.route('/ambulances')
def list_ambulances():
    ambulances = Ambulance.query.filter_by(is_available=True).all()
    return render_template('ambulances.html', ambulances=ambulances)

@app.route('/ambulance/register', methods=['POST'])
@login_required
def register_ambulance():
    ambulance = Ambulance(
        vehicle_number=request.form['vehicle_number'],
        driver_name=request.form['driver_name'],
        driver_contact=request.form['driver_contact'],
        type=request.form['type'],
        hospital_id=current_user.id
    )
    db.session.add(ambulance)
    db.session.commit()
    return jsonify({'success': True})

# Add a new route for the AI Health Assistant
@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message', '')
    
    # Create a more detailed prompt for the AI
    prompt = f"""You are a helpful medical assistant. Please provide accurate and helpful information 
    for the following health-related query. If this is an emergency, always advise to contact emergency 
    services or visit the nearest hospital immediately. Query: {user_message}"""
    
    try:
        response = model.generate_content(prompt)
        return jsonify({
            'response': response.text,
            'success': True
        })
    except Exception as e:
        return jsonify({
            'response': "I apologize, but I'm having trouble processing your request. For medical emergencies, please call emergency services immediately.",
            'success': False
        })

@app.route('/weather/<lat>/<lon>')
def get_weather(lat, lon):
    try:
        # Get current weather
        weather_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}&units=metric"
        weather_response = requests.get(weather_url)
        weather_data = weather_response.json()

        # Check for severe weather conditions
        alerts = []
        temp = weather_data['main']['temp']
        wind_speed = weather_data['wind']['speed']
        rain = weather_data.get('rain', {}).get('1h', 0)
        snow = weather_data.get('snow', {}).get('1h', 0)

        if temp < WEATHER_ALERTS['extreme_temp']['min']:
            alerts.append(f"Extreme cold temperature: {temp}°C")
        elif temp > WEATHER_ALERTS['extreme_temp']['max']:
            alerts.append(f"Extreme hot temperature: {temp}°C")

        if wind_speed > WEATHER_ALERTS['wind_speed']:
            alerts.append(f"High wind speed: {wind_speed} m/s")
        
        if rain > WEATHER_ALERTS['rain']:
            alerts.append(f"Heavy rainfall: {rain} mm")
        
        if snow > WEATHER_ALERTS['snow']:
            alerts.append(f"Heavy snowfall: {snow} mm")

        # If there are alerts, notify nearby hospitals
        if alerts:
            notify_nearby_hospitals(float(lat), float(lon), alerts)

        return jsonify({
            'current': {
                'temp': temp,
                'humidity': weather_data['main']['humidity'],
                'description': weather_data['weather'][0]['description'],
                'icon': weather_data['weather'][0]['icon']
            },
            'alerts': alerts
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def notify_nearby_hospitals(lat, lon, alerts):
    # Find hospitals within 15km radius
    nearby_hospitals = []
    for name, data in hospitals.items():
        hospital_lat = data['location']['lat']
        hospital_lng = data['location']['lng']
        distance = calculate_distance(lat, lon, hospital_lat, hospital_lng)
        if distance <= 15:
            nearby_hospitals.append({
                'name': name,
                'contact': data['contact'],
                'distance': distance
            })

    # In a real application, you would send notifications via email/SMS
    # For now, we'll just print the alerts
    for hospital in nearby_hospitals:
        print(f"Alert for {hospital['name']} ({hospital['distance']}km):")
        for alert in alerts:
            print(f"- {alert}")

def calculate_distance(lat1, lon1, lat2, lon2):
    from math import sin, cos, sqrt, atan2, radians
    R = 6371  # Earth's radius in kilometers

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    distance = R * c
    
    return distance

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 