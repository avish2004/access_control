from flask import Flask, request, jsonify, redirect, url_for, render_template, session
from werkzeug.security import generate_password_hash, check_password_hash
import json
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Data storage using JSON file
data_file = 'user_data.json'
if not os.path.exists(data_file):
    with open(data_file, 'w') as f:
        json.dump([], f)

# Utility functions to read/write data
def read_users():
    with open(data_file, 'r') as f:
        return json.load(f)

def write_users(users):
    with open(data_file, 'w') as f:
        json.dump(users, f, indent=4)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        # Hash the password
        hashed_password = generate_password_hash(password)

        users = read_users()

        # Check if user already exists
        if any(user['username'] == username for user in users):
            return 'User already exists!'

        # Append new user to the JSON data
        users.append({'username': username, 'password': hashed_password, 'role': role})
        write_users(users)

        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        users = read_users()

        # Find the user
        user = next((user for user in users if user['username'] == username), None)
        if user and check_password_hash(user['password'], password):
            session['username'] = username
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        else:
            return 'Invalid credentials!'

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', username=session['username'], role=session['role'])

@app.route('/deprovision', methods=['POST'])
def deprovision():
    if 'username' not in session or session['role'] != 'admin':
        return 'Access Denied'

    username_to_delete = request.form['username']
    users = read_users()

    # Delete the user if found
    users = [user for user in users if user['username'] != username_to_delete]
    write_users(users)

    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
