from flask import Flask, request, redirect, url_for, render_template, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
import datetime
from datetime import timedelta

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150),unique=True, nullable=False)
    password = db.Column(db.Text, nullable=False)
    role = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(150), nullable=True)
    student_id = db.Column(db.String(50), nullable=True)
    pending = db.Column(db.Boolean, default = True)  

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True, nullable=False)
    title = db.Column(db.String(150), nullable=False)
    author = db.Column(db.String(150), nullable=False)
    location = db.Column(db.String(150), nullable=False)
    available = db.Column(db.Boolean, default=True)
    time_added = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class BorrowRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    borrow_date = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    return_date = db.Column(db.DateTime, nullable=True)
    restore = db.Column(db.Boolean, default=False)
    user = db.relationship('User', backref='borrow_records', lazy=True)
    book = db.relationship('Book', backref='borrow_records', lazy=True)

# Initialize the database
with app.app_context():
    db.create_all()

# Role-based Access Control Decorator
def role_required(roles):
    def wrapper(func):
        def decorated_view(*args, **kwargs):
            if 'username' not in session:
                return redirect(url_for('login'))

            user_role = session.get('role')
            if user_role not in roles:
                return 'Access Denied', 403
            return func(*args, **kwargs)
        decorated_view.__name__ = func.__name__
        return decorated_view
    return wrapper

@app.route('/')
def home():
    return render_template('index.html')  # Rendered with index.html template

#User registration, once member has registered, POST request gets sent to libriarian for approval
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        name = request.form.get('name')
        student_id = request.form.get('student_id')

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        if User.query.filter_by(username=username).first():
            return 'User already exists!'

        # Set pending status to False for librarians and admins
        if role == 'student':
            new_user = User(username=username, password=hashed_password, role=role, name=name, student_id=student_id, pending=True)
        else:
            new_user = User(username=username, password=hashed_password, role=role, name=name, pending=False)
        
        db.session.add(new_user)
        db.session.commit()
        print('Registration successful. Please wait for approval if required.')
        return redirect(url_for('login'))
    return render_template('register.html')

#User login, if login request is succesful, routes user to dashboard
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if not user:
            return 'Invalid credentials!'  # User does not exist

        # If user exists, check password
        if not check_password_hash(user.password, password):
            return 'Invalid credentials!'  # Incorrect password

        # Check if the account is still pending approval
        if user.pending:
            return 'Account has not been verified by the librarian.'

        # Successful login
        session['username'] = username
        session['role'] = user.role
        return redirect(url_for('dashboard'))

    return render_template('login.html')  # Rendered with updated login.html template


# Dashboard that contains list of actions users can do depending on their permissions 
@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    role = session['role']
    books = Book.query.all()
    
    # Define feature access based on role
    borrow = role == 'student'
    can_manage_inventory = role in ['librarian', 'faculty']
    can_manage_members = role == 'librarian'
    can_view_members = role in ['faculty', 'librarian']
    can_issue_fines = role in ['faculty', 'librarian']
    approve = role == 'librarian'
    return1 = role == 'student'

    return render_template('dashboard.html', 
                           username=session['username'], 
                           role=role, 
                           books=books, 
                           borrow=borrow,
                           can_manage_inventory=can_manage_inventory,
                           can_manage_members=can_manage_members,
                           can_view_members=can_view_members,
                           can_issue_fines=can_issue_fines,
                           approve=approve,
                           return1 = return1) 

# Search Catalog - Available to All
@app.route('/search')
def search_catalog():
    books = Book.query.all()
    return render_template('catalog.html', books=books)  # Rendered with updated catalog.html template

@app.route('/borrow', methods=['GET','POST'])
@role_required(['student'])
def borrow():
    user = User.query.filter_by(username=session['username']).first()
    action = request.form.get('action')
    book_id = request.form.get('book_id')
    book = Book.query.get(book_id)
    books = Book.query.all()
    if request.method=='POST' and action == 'borrow':
        if book and book.available: 
            book.available = False
            new_borrow_record = BorrowRecord(user_id=user.id, book_id=book.id)
            db.session.add(new_borrow_record)
            db.session.commit()
            return redirect(url_for('dashboard'))
    return render_template('checkout.html', books = books)

# Return Book - Only for Students
@app.route('/return1', methods=['GET','POST'])
@role_required(['student'])
def return1():
    user = User.query.filter_by(username=session['username']).first()
    action = request.form.get('action')
    book_id = request.form.get('book_id')
    book = Book.query.get(book_id)
    if request.method=='POST' and action == 'return':
        if book and not book.available: 
            book.available = True
            BorrowRecord.query.filter_by(book_id=book.id, user_id = user.id).delete()
            db.session.commit()
            return redirect(url_for('dashboard'))
    
    books = Book.query.all()
    return render_template('checkin.html', books = books)

# Manage Inventory - Only for Librarians
@app.route('/inventory', methods=['GET', 'POST'])
@role_required(['librarian'])
def manage_inventory():
    if request.method == 'POST':
        title = request.form['title']
        author = request.form['author']
        location = request.form['location']

        new_book = Book(title=title, author=author, location=location)
        db.session.add(new_book)
        db.session.commit()
        return redirect(url_for('manage_inventory'))

    books = Book.query.all()
    return render_template('inventory.html', books=books)  # Rendered with updated inventory.html template

@app.route('/remove_book/<int:book_id>', methods=['POST'])
@role_required(['librarian'])
def remove_book(book_id):
    book = Book.query.get(book_id)
    if book:
        BorrowRecord.query.filter_by(book_id=book.id).delete()  # Delete all borrow records for the book
        db.session.delete(book)
        db.session.commit()
    return redirect(url_for('manage_inventory'))

# Manage Membership - Only for Librarians
@app.route('/manage_members', methods=['GET', 'POST'])
@role_required(['librarian'])
def manage_members():
    if request.method == 'POST':
        username_to_delete = request.form['username']
        user = User.query.filter_by(username=username_to_delete).first()
        if user:
            BorrowRecord.query.filter_by(user_id=user.id).delete()  # Delete all borrow records for the user
            db.session.delete(user)
            db.session.commit()
        return redirect(url_for('manage_members'))

    users = User.query.all()
    return render_template('members.html', users=users)  # Rendered with updated members.html template
#Approve new members - only for librarians

#It gives key error when I try to approve (brain blew up)
@app.route('/approve', methods=['GET', 'POST'])
@role_required(['librarian'])
def approve():
    if request.method == 'POST':
        username = request.form['username']
        action = request.form['action']  # 'approve' or 'reject'
        user = User.query.filter_by(username=username, pending=True).first()
        
        if user:
            if action == 'approve':
                user.pending = False  # Set 'pending' to False when approved
            elif action == 'reject':
                db.session.delete(user)  # Delete user if rejected
            db.session.commit()
        
        return redirect(url_for('approve'))

    pending_users = User.query.filter_by(pending=True).all()
    return render_template('approval.html', users=pending_users)

# View Member Data - Only for Faculty
@app.route('/view_members', methods=['GET'])
@role_required(['faculty','librarian'])
def view_members():
    users = User.query.all()
    return render_template('view_members.html', users=users)  # Rendered with updated view_members.html template

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)