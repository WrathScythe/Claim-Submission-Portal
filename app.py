import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask import render_template_string
from models import db, User, ClaimType, Claim, NotificationTemplate
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL',
    'postgresql://claimuser:claimpass@localhost:5432/claimdb'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ============================================================
# AUTHENTICATION ROUTES
# ============================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        flash('Invalid username or password', 'error')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'staff')

        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return redirect(url_for('register'))

        user = User(username=username, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful. Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ============================================================
# DASHBOARD
# ============================================================

@app.route('/')
@login_required
def dashboard():
    if current_user.is_oic():
        return redirect(url_for('oic_dashboard'))
    user_claims = Claim.query.filter_by(user_id=current_user.id).order_by(Claim.created_at.desc()).all()
    claim_types = ClaimType.query.filter_by(is_active=True).all()
    return render_template('dashboard.html', claims=user_claims, claim_types=claim_types)


# ============================================================
# CLAIM SUBMISSION (Normal Staff)
# ============================================================

@app.route('/submit-claim', methods=['GET', 'POST'])
@login_required
def submit_claim():
    if current_user.is_oic():
        flash('OIC staff do not submit claims', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        claim_type_id = request.form.get('claim_type_id')
        title = request.form.get('title')
        description = request.form.get('description')
        amount = request.form.get('amount')
        additional_details = request.form.get('additional_details', '')

        # VULNERABILITY: Stored XSS
        # No input sanitisation - description and additional_details are stored as-is
        # When OIC reviews, these fields render raw HTML/JS via |safe filter
        claim = Claim(
            user_id=current_user.id,
            claim_type_id=claim_type_id,
            title=title,
            description=description,
            amount=float(amount),
            additional_details=additional_details,
            status='pending'
        )
        db.session.add(claim)
        db.session.commit()
        flash('Claim submitted successfully!', 'success')
        return redirect(url_for('dashboard'))

    claim_types = ClaimType.query.filter_by(is_active=True).all()
    return render_template('submit_claim.html', claim_types=claim_types)


# ============================================================
# CLAIM SEARCH - VULNERABLE TO SQL INJECTION
# ============================================================

@app.route('/search-claims', methods=['GET', 'POST'])
@login_required
def search_claims():
    results = []
    search_query = ''
    is_raw_sql = False

    if request.method == 'POST':
        search_query = request.form.get('search', '')

        if search_query:
            # VULNERABILITY: SQL Injection
            # User input is directly concatenated into the SQL query
            # A staff user can inject SQL to extract other users' claims or credentials
            # Example injection payload (staff user):
            #   ' UNION SELECT id, username, email, password_hash, role, null, null, null, null, null, null, null, null FROM users --
            if current_user.is_oic():
                raw_query = "SELECT * FROM claims WHERE title LIKE '%" + search_query + "%' OR description LIKE '%" + search_query + "%' ORDER BY created_at DESC"
            else:
                raw_query = "SELECT * FROM claims WHERE user_id = " + str(current_user.id) + " AND (title LIKE '%" + search_query + "%' OR description LIKE '%" + search_query + "%') ORDER BY created_at DESC"

            try:
                results = db.session.execute(db.text(raw_query)).fetchall()
                is_raw_sql = True
            except Exception as e:
                flash(f'Query error: {e}', 'error')
                results = []
        else:
            if current_user.is_oic():
                results = Claim.query.order_by(Claim.created_at.desc()).all()
            else:
                results = Claim.query.filter_by(user_id=current_user.id).order_by(Claim.created_at.desc()).all()
    else:
        if current_user.is_oic():
            results = Claim.query.order_by(Claim.created_at.desc()).all()
        else:
            results = Claim.query.filter_by(user_id=current_user.id).order_by(Claim.created_at.desc()).all()

    return render_template('search_claims.html', results=results, search_query=search_query, is_raw_sql=is_raw_sql)


@app.route('/claim/<int:claim_id>')
@login_required
def view_claim(claim_id):
    claim = Claim.query.get_or_404(claim_id)
    # Staff can only view their own claims, OIC can view all
    if not current_user.is_oic() and claim.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    return render_template('view_claim.html', claim=claim)


# ============================================================
# CLAIM APPROVAL - VULNERABLE: Broken Approval Workflow
# ============================================================

@app.route('/claim/<int:claim_id>/approve', methods=['POST'])
@login_required
def approve_claim(claim_id):
    # VULNERABILITY: Broken Approval Workflow
    # The server does NOT enforce role check here.
    # Only a hidden form field / client-side button visibility restricts this,
    # but a normal staff user can tamper with the request or call this endpoint directly
    # to approve their own claim.

    # NOTE: No server-side role enforcement — any logged-in user can approve/reject
    claim = Claim.query.get_or_404(claim_id)
    action = request.form.get('action')  # 'approve' or 'reject'
    review_notes = request.form.get('review_notes', '')

    if action == 'approve':
        claim.status = 'approved'
    elif action == 'reject':
        claim.status = 'rejected'
    else:
        flash('Invalid action', 'error')
        return redirect(url_for('view_claim', claim_id=claim_id))

    claim.reviewed_by = current_user.id
    claim.review_notes = review_notes
    claim.updated_at = datetime.utcnow()
    db.session.commit()

    # VULNERABILITY: SSTI - Render notification using stored template
    _render_claim_notification(claim)

    flash(f'Claim {action}d successfully!', 'success')
    return redirect(url_for('oic_dashboard') if current_user.is_oic() else url_for('dashboard'))


def _render_claim_notification(claim):
    """Render notification using the stored template - VULNERABLE TO SSTI"""
    template = NotificationTemplate.query.filter_by(is_active=True).first()
    if template:
        try:
            # VULNERABILITY: SSTI (Server-Side Template Injection)
            # The stored template is rendered with render_template_string
            # An attacker with OIC access can modify the template to include
            # Jinja2 SSTI payloads like {{config}} or {{''.__class__.__mro__[1].__subclasses__()}}
            rendered = render_template_string(
                template.template_content,
                claim_data=claim,
                claim_title=claim.title,
                claim_amount=claim.amount,
                claim_status=claim.status,
                submitter_name=claim.submitter.username,
                claim_id=claim.id
            )
            # In a real app this would send an email; here we just log it
            print(f"Notification rendered for claim {claim.id}: {rendered[:100]}...")
        except Exception as e:
            print(f"Template rendering error: {e}")


# ============================================================
# OIC STAFF ROUTES
# ============================================================

@app.route('/oic')
@login_required
def oic_dashboard():
    if not current_user.is_oic():
        flash('Access denied. OIC staff only.', 'error')
        return redirect(url_for('dashboard'))
    pending_claims = Claim.query.filter_by(status='pending').order_by(Claim.created_at.desc()).all()
    all_claims = Claim.query.order_by(Claim.created_at.desc()).limit(50).all()
    claim_types = ClaimType.query.all()
    return render_template('oic/dashboard.html',
                           pending_claims=pending_claims,
                           all_claims=all_claims,
                           claim_types=claim_types)


@app.route('/oic/manage-claim-types', methods=['GET', 'POST'])
@login_required
def manage_claim_types():
    if not current_user.is_oic():
        flash('Access denied. OIC staff only.', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'create':
            name = request.form.get('name')
            description = request.form.get('description')
            required_fields = request.form.get('required_fields', '')
            claim_type = ClaimType(name=name, description=description, required_fields=required_fields)
            db.session.add(claim_type)
            db.session.commit()
            flash('Claim type created!', 'success')

        elif action == 'toggle':
            ct_id = request.form.get('claim_type_id')
            ct = ClaimType.query.get(ct_id)
            ct.is_active = not ct.is_active
            db.session.commit()
            flash(f'Claim type {"activated" if ct.is_active else "deactivated"}!', 'success')

        elif action == 'delete':
            ct_id = request.form.get('claim_type_id')
            ct = ClaimType.query.get(ct_id)
            db.session.delete(ct)
            db.session.commit()
            flash('Claim type deleted!', 'success')

        return redirect(url_for('manage_claim_types'))

    claim_types = ClaimType.query.all()
    return render_template('oic/manage_claim_types.html', claim_types=claim_types)


@app.route('/oic/review-claims')
@login_required
def review_claims():
    if not current_user.is_oic():
        flash('Access denied. OIC staff only.', 'error')
        return redirect(url_for('dashboard'))
    claims = Claim.query.order_by(Claim.created_at.desc()).all()
    return render_template('oic/review_claims.html', claims=claims)


@app.route('/oic/review-claim/<int:claim_id>')
@login_required
def review_claim(claim_id):
    if not current_user.is_oic():
        flash('Access denied. OIC staff only.', 'error')
        return redirect(url_for('dashboard'))
    claim = Claim.query.get_or_404(claim_id)
    # VULNERABILITY: Stored XSS - The claim description/additional_details
    # are rendered with |safe in the template, allowing stored XSS to execute
    return render_template('oic/review_claim.html', claim=claim)


# ============================================================
# OIC NOTIFICATION TEMPLATE CUSTOMIZATION - SSTI VULNERABLE
# ============================================================

@app.route('/oic/customize-claim-notification', methods=['GET', 'POST'])
@login_required
def customize_claim_notification():
    if not current_user.is_oic():
        flash('Access denied. OIC staff only.', 'error')
        return redirect(url_for('dashboard'))

    template = NotificationTemplate.query.filter_by(is_active=True).first()

    if request.method == 'POST':
        template_content = request.form.get('template_content')
        template_name = request.form.get('template_name', 'Claim Notification')

        if template:
            # VULNERABILITY: SSTI
            # Template content is stored directly without sanitisation
            # When rendered with render_template_string, Jinja2 SSTI payloads execute
            template.template_content = template_content
            template.name = template_name
            template.updated_by = current_user.id
        else:
            template = NotificationTemplate(
                name=template_name,
                template_content=template_content,
                is_active=True,
                updated_by=current_user.id
            )
            db.session.add(template)

        db.session.commit()
        flash('Notification template updated!', 'success')
        return redirect(url_for('customize_claim_notification'))

    default_template = """<h2>Claim Notification</h2>
<p>Claim #{{ claim_id }} has been {{ claim_status }}.</p>
<p><strong>Title:</strong> {{ claim_title }}</p>
<p><strong>Amount:</strong> ${{ claim_amount }}</p>
<p><strong>Submitted by:</strong> {{ submitter_name }}</p>
<p>Thank you.</p>"""

    return render_template('oic/customize_notification.html',
                           template=template,
                           default_template=default_template)


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_database():
    """Initialize database with tables and default data"""
    db.create_all()

    # Create default OIC admin user if not exists
    if not User.query.filter_by(username='oic_admin').first():
        admin = User(username='oic_admin', email='oic@example.com', role='oic')
        admin.set_password('oic_admin_pass')
        db.session.add(admin)

    # Create a demo staff user if not exists
    if not User.query.filter_by(username='staff_user').first():
        staff = User(username='staff_user', email='staff@example.com', role='staff')
        staff.set_password('staff_pass')
        db.session.add(staff)

    # Create default claim types if none exist
    if ClaimType.query.count() == 0:
        types = [
            ClaimType(name='Travel Expenses', description='Reimbursement for work-related travel',
                      required_fields='destination,dates,purpose'),
            ClaimType(name='Medical Expenses', description='Medical and health-related claims',
                      required_fields='diagnosis,provider,treatment_date'),
            ClaimType(name='Equipment Purchase', description='Office equipment and supplies',
                      required_fields='item,vendor,justification'),
            ClaimType(name='Training & Development', description='Training courses and certifications',
                      required_fields='course_name,provider,cost_breakdown'),
        ]
        db.session.add_all(types)

    # Create default notification template if none exists
    if NotificationTemplate.query.count() == 0:
        default_notif = NotificationTemplate(
            name='Claim Approval Notification',
            template_content="""<h2>Claim Notification</h2>
<p>Claim #{{ claim_id }} has been {{ claim_status }}.</p>
<p><strong>Title:</strong> {{ claim_title }}</p>
<p><strong>Amount:</strong> ${{ claim_amount }}</p>
<p><strong>Submitted by:</strong> {{ submitter_name }}</p>
<p>Thank you.</p>""",
            is_active=True
        )
        db.session.add(default_notif)

    db.session.commit()
    print("Database initialized with default data.")


if __name__ == '__main__':
    with app.app_context():
        init_database()
    app.run(host='0.0.0.0', port=5000, debug=True)
else:
    # Initialise database when loaded by gunicorn or other WSGI servers
    with app.app_context():
        try:
            init_database()
        except Exception as e:
            print(f"Database init deferred or failed: {e}")
            print("Run 'python -c \"from app import app, init_database; app.app_context().push(); init_database()\"' to initialise manually.")

