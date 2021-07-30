from flask import Flask, render_template, request, session, redirect, url_for, abort, flash
from flask_sqlalchemy import SQLAlchemy 
from passlib.hash import sha256_crypt
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
db = SQLAlchemy(app)

#For Password encrypt
app.secret_key = 'divyatest123'

# Create a User Model Class
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(25), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    image_file = db.Column(db.String(20), default='default.jpg')
    password = db.Column(db.String(64), nullable=False)
    posts = db.relationship('Post', backref='author', lazy=True)
    bookmarked = db.relationship('Bookmark',backref='saved_by',lazy=True)

    def __repr__(self):
        return f"User ('{self.username}', '{self.email}', '{self.id}')"

# Post model
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# BookMark Model
class Bookmark(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'),default=None)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'),default=None)

# Likes Table
likes = db.Table('likes',
                 db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
                 db.Column('post_id', db.Integer, db.ForeignKey('post.id'))
                 )

# Returns current user
def current_user():
    if len(session) > 0:
        return User.query.filter_by(username=session['username']).first()
    else:
        return None
        
########################## ROUTES #####################

#Start by Default
@app.route('/')
def index():    
    db.create_all();
    session['logged_in'] = False
    return render_template('start.html')   
    
#Home route 
@app.route('/home')
def home():
    #posts = Post.query.filter_by(comment=None).all()
    posts = Post.query.all()
    follow_suggestions = User.query.all()[0:7]
    if current_user(): 
        if current_user() in follow_suggestions:
            follow_suggestions.remove(current_user())
    return render_template('home.html', posts=posts, user=current_user(), Post_model=Post,Bookmark_model=Bookmark, likes=likes, follow_suggestions=follow_suggestions, User=User)

# Register route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST': 
        username = request.form['username']
        email = request.form['email'].lower()
        password = sha256_crypt.encrypt(str(request.form['password']))
        user = User(username=username, email=email, password=password)
        db.session.add(user)
        db.session.commit()
        #flash('You are now registered and can log in', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

# User login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].lower()
        password_candidate = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user != None:
            password = user.password
            if sha256_crypt.verify(password_candidate, password):
                session['logged_in'] = True
                session['username'] = user.username
                session['user_id'] = user.id
                #flash('You are now logged in', 'success')
                return redirect(url_for('home'))
            else:
                error = 'Invalid password'
                return render_template('login.html', error=error)
        else:
            error = 'Email not found'
            return render_template('login.html', error=error)
    else:
            return render_template('login.html')

# Check if user logged in
def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            return redirect(url_for('login'))
    return wrap

# Logout
@app.route('/logout')
@is_logged_in
def logout():
    session.clear()
    #flash('You are now logged out', 'success')
    return redirect(url_for('index'))    

# Add Tweet
@app.route('/new_post/', methods=['GET', 'POST'])
@is_logged_in
def new_post():
    if request.method == 'POST':
        content = request.form['content']
        post = Post(content=content, author=current_user())
        db.session.add(post)
        db.session.commit()
        #flash('Your new post has been created!', 'success')
        return redirect(url_for('home'))
    return render_template('new_post.html',title='New post')

# Search Tweet
@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        query = request.form['search']
        posts = Post.query.filter(Post.content.like('%' + query + '%'))
        return render_template('results.html', posts=posts, Post_model=Post, user=current_user(),title='Searched Tweets Containing : ' + query)

# Bookmark post
@app.route('/bookmark/<int:post_id>')
def save_post(post_id):
    if Bookmark.query.filter_by(post_id=post_id).first() != None:        
        db.session.delete(Bookmark.query.filter_by(post_id=post_id).first())
        db.session.commit()
    else:
        db.session.add(Bookmark(post_id=post_id,user_id=current_user().id))
        db.session.commit()
    return redirect(url_for('home'))

# Sort Tweet in Ascending
@app.route('/sortAsc')
def sortAsc():
        posts = Post.query.order_by(Post.date_posted.asc()) 
        return render_template('results.html', posts=posts, Post_model=Post, user=current_user(),title='Tweets Sorted in Chronological Order')

# Sort Tweet in Descending
@app.route('/sortDesc')
def sortDesc():
        posts = Post.query.order_by(Post.date_posted.desc()) 
        return render_template('results.html', posts=posts, Post_model=Post, user=current_user(),title='Tweets Sorted in Chronological Order')

# Filter Tweet
@app.route('/filter')
def filter():
        posts = Post.query.filter(Post.user_id==current_user().id) 
        return render_template('results.html', posts=posts, Post_model=Post, user=current_user(),title='Tweets Filtered By Current User')

# Delete Tweet
@app.route('/delete_tweet/<int:post_id>')
@is_logged_in
def delete_tweet(post_id):
    post = Post.query.filter_by(id=post_id).first()
    post = Post.query.get_or_404(post_id)  
    if post.author.id != current_user().id:
        abort(403)
    db.session.delete(post)
    db.session.commit()
    return redirect(url_for('home'))


# Error Route
@app.errorhandler(404)
def error404(error):
    return render_template('404.html'), 404

if __name__ == "__main__":
    app.run(debug=True) 
