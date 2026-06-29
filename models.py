from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='staff')  # 'staff' or 'oic'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    claims = db.relationship('Claim', backref='submitter', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_oic(self):
        return self.role == 'oic'


class ClaimType(db.Model):
    __tablename__ = 'claim_types'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    required_fields = db.Column(db.Text)  # JSON string of required fields
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    claims = db.relationship('Claim', backref='claim_type', lazy=True)


class Claim(db.Model):
    __tablename__ = 'claims'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    claim_type_id = db.Column(db.Integer, db.ForeignKey('claim_types.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)  # VULNERABLE: Stored XSS - no sanitisation
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    additional_details = db.Column(db.Text)  # VULNERABLE: Stored XSS - no sanitisation
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    review_notes = db.Column(db.Text)

    reviewer = db.relationship('User', foreign_keys=[reviewed_by])


class NotificationTemplate(db.Model):
    __tablename__ = 'notification_templates'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    template_content = db.Column(db.Text, nullable=False)  # VULNERABLE: SSTI - rendered with render_template_string
    is_active = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
