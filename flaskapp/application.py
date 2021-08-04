from flask import Flask, render_template, request, session, redirect, url_for, abort
from flask_sqlalchemy import SQLAlchemy 
from passlib.hash import sha256_crypt
from datetime import datetime
from functools import wraps
import logging
import os

application = Flask(__name__)
application.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'
application.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
application.config["SESSION_PERMANENT"] = False 
db = SQLAlchemy(application)

logging.basicConfig(filename='records.log', level=logging.DEBUG, format=f'%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s')
 
#For Password encrypt
application.secret_key = os.urandom(24)

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

# Check if user logged in
def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            application.logger.warning('Unauthorized, Please login!')
            return redirect(url_for('login'))
    return wrap

########################## ROUTES #####################

#Start by Default
@application.route('/')
def index():   
    try:
        db.create_all();
        session.clear()
        session['logged_in'] = False 
        application.logger.info(' Welcome to Tweeeter!!! ')            
        return render_template('start.html') 
    except Exception as e:
	    abort(403)

#Home route 
@application.route('/home')
@is_logged_in
def home():
    try:
        posts = Post.query.all()
        if len(posts) != 0:
            follow_suggestions = User.query.all()[0:7]            
            if current_user(): 
                if current_user() in follow_suggestions:
                    follow_suggestions.remove(current_user())
            return render_template('home.html', posts=posts, user=current_user(), Post_model=Post,Bookmark_model=Bookmark, likes=likes, follow_suggestions=follow_suggestions, User=User)
        else:
            session['nopost'] = True
            error = ' Sorry, There are no tweets to display from DB. Try adding a new post! '
            application.logger.warning(error)
            return render_template("500.html", error = error) 
    except Exception as e:
        if len(Post.query.all()) == 0:
            session['no_post'] = True
            error = ' Sorry, There are no tweets to display from DB. Try adding a new post! '
            application.logger.warning(error)
            return render_template("500.html", error = error) 
        else:
            error =' Unauthorized, Please login and try again! '
            application.logger.warning(error)
            return render_template("500.html", error = error) 

# Register route
@application.route('/register', methods=['GET', 'POST'])
def register():
    try:
        if request.method == 'POST': 
            username = request.form['username']
            email = request.form['email'].lower()
            password = sha256_crypt.encrypt(str(request.form['password']))
            user = User(username=username, email=email, password=password)
            db.session.add(user)
            db.session.commit()
            application.logger.info('%s , You are now registered and can log in!!!', username)
            return redirect(url_for('login'))
        return render_template('register.html')
    except Exception as e:        
        abort(403)

# User login
@application.route('/login', methods=['GET', 'POST'])
def login():
    try:
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
                    application.logger.info(' %s logged in successfully!!! ', user.username)
                    return redirect(url_for('home'))
                else:
                    error = ' Invalid password!!! '
                    application.logger.error(error)
                    return render_template("500.html", error = error) 
            else:
                error = ' Email not found!!! '
                application.logger.error(error)
                return render_template("500.html", error = error) 
        else:
                return render_template('login.html')
    except Exception as e:
        abort(403)

# Logout
@application.route('/logout')
@is_logged_in
def logout():
    application.logger.info('%s , You are now logged out!!!', session['username']) 
    if 'no_post' in session: 
        session.pop('no_post')  
    session.clear()
    return redirect(url_for('index'))    

# Add Tweet
@application.route('/new_post/', methods=['GET', 'POST'])
@is_logged_in
def new_post():
    try:
        if request.method == 'POST':
            content = request.form['content']
            post = Post(content=content, author=current_user())
            db.session.add(post)
            db.session.commit()
            application.logger.info(' Your new post has been created! ')
            return redirect(url_for('home'))
        return render_template('new_post.html',title=' New post! ')
    except Exception as e:
        abort(403)

# Search Tweet
@application.route('/search', methods=['GET', 'POST'])
@is_logged_in
def search():
    try:
        if request.method == 'POST':
            query = request.form['search']
            posts = Post.query.filter(Post.content.like('%' + query + '%'))
            if posts.count() == 0:   
                error = ' No searched results found for tweets containing : ' + query  + '!!'
                application.logger.info(error)
                return render_template("500.html", error = error)    
            else:
                title = ' Searched Tweets Containing ' + query + '!!'
                application.logger.info(title)
                return render_template('results.html', posts=posts, Post_model=Post, user=current_user(),title=title)
    except Exception as e:
        abort(403)

# Bookmark post
@application.route('/bookmark/<int:post_id>')
@is_logged_in
def save_post(post_id):
    try:
        if Bookmark.query.filter_by(post_id=post_id).first() != None:        
            db.session.delete(Bookmark.query.filter_by(post_id=post_id).first())
            application.logger.info(' Bookmark for post %s Removed! ',post_id)
            db.session.commit()
        else:
            db.session.add(Bookmark(post_id=post_id,user_id=current_user().id))
            application.logger.info(' Bookmark for post %s Added! ',post_id)
            db.session.commit()
        return redirect(url_for('home'))
    except Exception as e:
        abort(403)

# Sort Tweet in Ascending
@application.route('/sortAsc')
@is_logged_in
def sortAsc():
        posts = Post.query.order_by(Post.date_posted.asc()) 
        if posts.count() !=0:
            title = ' Tweets Sorted in Ascending Order! '
            application.logger.info(title)
        else:
            session['nopost'] = True
            error = ' Sorry, There are no tweets to display from DB. Try adding a new post! '
            application.logger.warning(error)
            return render_template("500.html", error = error)
        return render_template('results.html', posts=posts, Post_model=Post, user=current_user(),title=title)

# Sort Tweet in Descending
@application.route('/sortDesc')
@is_logged_in
def sortDesc():
        posts = Post.query.order_by(Post.date_posted.desc()) 
        if posts.count() !=0:
            title = ' Tweets Sorted in Descending Order! '
            application.logger.info(title)
        else:
            session['nopost'] = True
            error = ' Sorry, There are no tweets to display from DB. Try adding a new post! '
            application.logger.warning(error)
            return render_template("500.html", error = error)
        return render_template('results.html', posts=posts, Post_model=Post, user=current_user(),title=title)

# Filter Tweet
@application.route('/filter')
@is_logged_in
def filter():
    try:
        posts = Post.query.filter(Post.user_id==current_user().id) 
        if posts.count() != 0:
            title = ' Tweets Filtered By Current User! '
            application.logger.info(title)
            return render_template('results.html', posts=posts, Post_model=Post, user=current_user(),title=title)
        else:
            session['no_post'] = True
            error = ' Sorry, There are no tweets to display from DB. Try adding a new post! '
            application.logger.warning(error)
            return render_template("500.html", error = error)
    except Exception as e:
        abort(403)

# Delete Tweet
@application.route('/delete_tweet/<int:post_id>')
@is_logged_in
def delete_tweet(post_id):
    try:
        post = Post.query.filter_by(id=post_id).first()
        post = Post.query.get_or_404(post_id)  
        if post.author.id != current_user().id:
            error = ' You are not authorized to delete other users post! '
            application.logger.warning(error)
            return render_template("500.html", error = error)   
        db.session.delete(post)
        db.session.commit()
        application.logger.info(' Post %s deleted by %s !!', post.id,post.author.username)
        return redirect(url_for('home'))
    except Exception as e:
        abort(403)


# ======================================================

# Error Handling
@application.errorhandler(404)
def error404(error):    
    error =" Functionality not included! "
    application.logger.error(f"Server error: {error}, route: {request.url}")
    if session['logged_in'] == True:
        return render_template('404.html'), 404
    else:
         return render_template("500.html", error = str(error))

@application.errorhandler(403)
def error403(error):    
    application.logger.error(f" Server error: {error}, route: {request.url} ")
    return render_template("500.html", error = str(error)) 

# ==========================

if __name__ == "__main__":
    application.logger.error('Error level log')
    application.logger.info('Info level log')
    application.logger.warning('Warning level log')
    application.run(host ='0.0.0.0', debug = True) 
