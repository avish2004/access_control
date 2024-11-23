@app.route('/approve', methods =['GET', 'POST'])
@role_required(['librarian'])
def can_approve():
    if request.method == 'POST':
        user_to_approve = request.form['username']
        user = User.query.filter_by(username=user_to_approve).first()
        if user and user.pending == 0:
            user.pending = 1   
            db.session.commit()
        return redirect(url_for('approve'))

    users = User.query.all()
    return render_template('approval.html', users=users) 
