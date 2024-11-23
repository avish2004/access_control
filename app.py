from flask import Flask, request, redirect, url_for, render_template, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
import datetime

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
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    author = db.Column(db.String(150), nullable=False)
    location = db.Column(db.String(150), nullable=False)
    available = db.Column(db.Boolean, default=True)
    time_added = db.Column(db.DateTime, default=datetime.datetime.now)

class BorrowRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    book_id = db.Column(db.Integer, nullable=False)
    borrow_date = db.Column(db.DateTime, default=datetime.datetime.now)
    return_date = db.Column(db.DateTime, nullable=True)

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

        if role == 'student':
            new_user = User(username=username, password=hashed_password, role=role, name=name, student_id=student_id)
        else:
            new_user = User(username=username, password=hashed_password, role=role, name=name)
        db.session.add(new_user)
        db.session.commit()

        return 'Registration submitted for approval'
        return redirect(url_for('login'))
    return render_template('register.html')  # Rendered with updated register.html template


#User login, if login request is succesful, routes user to dashboard
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password) and user.pending == 1:
            session['username'] = username
            session['role'] = user.role

            # Redirect to dashboard after successful login
            return redirect(url_for('dashboard'))
        elif user.pending == 0:
            return 'Account has not been verfied by the librarian'
        else:
            return 'Invalid credentials!'

    return render_template('login.html')  # Rendered with updated login.html template

#Dashboard that contains list of actions users can do depending on their permissions 
@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    role = session['role']
    books = Book.query.all()
    
    # Define feature access based on role
    can_borrow_books = role == 'student'
    can_manage_inventory = role == 'librarian','faculty'
    can_manage_members = role == 'librarian'
    can_view_members = role == 'faculty'
    can_issue_fines = role == 'faculty'
    approve = role == 'librarian'
    return render_template('dashboard.html', 
                           username=session['username'], 
                           role=role, 
                           books=books, 
                           can_borrow_books=can_borrow_books,
                           can_manage_inventory=can_manage_inventory,
                           can_manage_members=can_manage_members,
                           can_view_members=can_view_members,
                           approve = approve)  # Rendered with updated dashboard.html template

# Search Catalog - Available to All
@app.route('/search')
def search_catalog():
    books = Book.query.all()
    return render_template('catalog.html', books=books)  # Rendered with updated catalog.html template

# Borrow Book - Only for Students
@app.route('/borrow/<int:book_id>', methods=['POST'])
@role_required(['student'])
def borrow(book_id):
    user = User.query.filter_by(username=session['username']).first()
    book = Book.query.get(book_id)

    if book and book.available:
        book.available = False
        new_borrow_record = BorrowRecord(user_id=user.id, book_id=book.id)
        db.session.add(new_borrow_record)
        db.session.commit()
        return redirect(url_for('checkout'))

    return 'Book not available!'
    return render_template('checkout.html', books=books)  # Rendered with updated inventory.html template

# Return Book - Only for Students
@app.route('/return/<int:book_id>', methods=['POST'])
@role_required(['student'])
def return_book(book_id):
    user = User.query.filter_by(username=session['username']).first()
    borrow_record = BorrowRecord.query.filter_by(user_id=user.id, book_id=book_id, return_date=None).first()
    book = Book.query.get(book_id)

    if borrow_record and book:
        borrow_record.return_date = datetime.datetime.now()
        book.available = True
        db.session.commit()
        return redirect(url_for('dashboard'))

    return 'Book not borrowed by user!'

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
        user_to_approve = request.form['username']  # Get the username from the form
        user = User.query.filter_by(username=user_to_approve).first()  # Query by the username
        if user:
            user.pending = True  # Set 'pending' to True when approved
            db.session.commit()  # Commit the change to the database
        return redirect(url_for('approve'))  # Redirect to reload the page

    users = User.query.all()
    return render_template('approval.html', user=users) 


# View Member Data - Only for Faculty
@app.route('/view_members', methods=['GET'])
@role_required(['faculty'])
def view_members():
    users = User.query.all()
    return render_template('view_members.html', users=users)  # Rendered with updated view_members.html template

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
