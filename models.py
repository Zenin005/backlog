from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Hospital(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200))
    address = db.Column(db.String(200))
    contact_number = db.Column(db.String(20))
    total_beds = db.Column(db.Integer, default=0)
    available_beds = db.Column(db.Integer, default=0)
    oxygen_cylinders = db.Column(db.Integer, default=0)
    icu_beds = db.Column(db.Integer, default=0)
    emergency_status = db.Column(db.String(20), default='available')
    specialties = db.Column(db.String(500))  # Stored as comma-separated values
    rating = db.Column(db.Float, default=4.0)
    location_lat = db.Column(db.Float)
    location_lng = db.Column(db.Float)
    ambulances = db.relationship('Ambulance', backref='hospital', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'address': self.address,
            'contact': self.contact_number,
            'available_beds': self.available_beds,
            'total_beds': self.total_beds,
            'oxygen_cylinders': self.oxygen_cylinders,
            'icu_beds': self.icu_beds,
            'emergency_status': self.emergency_status,
            'specialties': self.specialties.split(',') if self.specialties else [],
            'rating': self.rating,
            'location': {'lat': self.location_lat, 'lng': self.location_lng}
        }

class Ambulance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_number = db.Column(db.String(20), unique=True)
    driver_name = db.Column(db.String(100))
    driver_contact = db.Column(db.String(20))
    is_available = db.Column(db.Boolean, default=True)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospital.id'))
    type = db.Column(db.String(50))  # Basic, Advanced, etc. 