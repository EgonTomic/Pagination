import hashlib
import uuid
import os
import smartninja_redis
from flask import Flask, render_template, request, redirect, url_for, make_response
from models.user import User
from models.topic import Topic
from models.settings import db
import math

app = Flask(__name__)

# Create tables in database
db.create_all()

# Create redis database caching purposes
redis = smartninja_redis.from_url(os.environ.get("REDIS_URL"))

@app.route("/")
def index():
    # Check if user is authenticated based on session_token
    session_token = request.cookies.get("session_token")
    user = db.query(User).filter_by(session_token=session_token).first()

    # Get number of page from URL argument
    try:
        page_number = int(request.args.get("page", 1))
    except ValueError:
        page_number = 1
    page_number = max(1, page_number)

    # Basic query
    base_query = db.query(Topic)
    total_topics = base_query.count()

    # Adding ordering
    topic_query = base_query.order_by(Topic.id.desc())

    # Parameters pagination
    per_page = 5
    num_pages = math.ceil(total_topics / per_page)
    
    offset = (page_number - 1) * per_page
    
    topics = topic_query.limit(per_page).offset(offset).all()

    page_obj = type("PageObj", (), {})()  # Creating empty object
    page_obj.number = page_number
    page_obj.object_list = topics
    page_obj.has_previous = page_number > 1
    page_obj.has_next = page_number < num_pages
    page_obj.previous_page_number = page_number - 1 if page_obj.has_previous else 1
    page_obj.next_page_number = page_number + 1 if page_obj.has_next else num_pages

    return render_template("index.html", user=user, topics=topics, page_obj=page_obj,num_pages=num_pages, total_topics=total_topics)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    elif request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # Calculate hashed password based on plan text input from login form
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        # Get user from database base on username from login form
        user = db.query(User).filter_by(username=username).first()

        if not user:
            return "Username or password is incorrect."
        else:
            # If user exists, check if password hashes match
            if password_hash == user.password_hash:
                user.session_token = str(uuid.uuid4())
                db.add(user)
                db.commit()

                # Save user session token into cookie
                response = make_response(redirect(url_for("index")))
                response.set_cookie("session_token", user.session_token)

                return response
            else:
                return "Username or password is incorrect."

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")
    elif request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        repeated_password = request.form.get("repeatpassword")

        if password != repeated_password:
            return "Passwords don't match. Please try again."

        print("New user username: " + username)
        print("New user password: " + password)
        print("New user repeat password: " + repeated_password)

        user = User(username=username, password_hash=hashlib.sha256(password.encode()).hexdigest(), 
                    session_token=str(uuid.uuid4()))
        
        db.add(user)
        db.commit()

        response = make_response(redirect(url_for("index")))
        response.set_cookie("session_token", user.session_token)
 
        return response
    
@app.route("/create-topic", methods=["GET", "POST"])
def topic_create():
    # Check if user is authenticated based on session_token
    session_token = request.cookies.get("session_token")
    user = db.query(User).filter_by(session_token=session_token).first()
    
    if not user:
        return redirect(url_for("login"))
    
    if request.method == "GET":
        csrf_token = str(uuid.uuid4())
        redis.set(name=csrf_token, value=user.username)

        return render_template("topic_create.html", user=user, csrf_token=csrf_token)
    elif request.method == "POST":
        csrf_token = request.form.get('csrf_token')
        title = request.form.get('title')
        text = request.form.get('text')

        redis_csrf_username = redis.get(name=csrf_token)

        if redis_csrf_username and redis_csrf_username.decode() == user.username:
            # Create new topic object
            user = db.query(User).filter_by(session_token=session_token).first()
            topic = Topic.create(title=title, text=text, author=user)
            return redirect(url_for("index"))
        else:
            return redirect(url_for("login"))
    
@app.route("/topic/<topic_id>", methods=["GET"])
def topic_details(topic_id):
    # Check if user is authenticated based on session_token
    session_token = request.cookies.get("session_token")
    user = db.query(User).filter_by(session_token=session_token).first()

    topic = db.query(Topic).get(int(topic_id))

    return render_template("topic_details.html", topic=topic, user=user)

@app.route("/topic/<topic_id>/edit", methods=["GET", "POST"])
def topic_edit(topic_id):
    # Check if user is autheticaed based on session_token
    session_token = request.cookies.get("session_token")
    user = db.query(User).filter_by(session_token=session_token).first()

    if not user:
        return redirect(url_for("index"))
    
    topic = db.query(Topic).get(int(topic_id))

    if user.id != topic.author.id:
        return redirect(url_for("index"))
    
    if request.method == "GET":
        return render_template("topic_edit.html", topic=topic, user=user)
    elif request.method == "POST":
        title = request.form.get("title")
        text = request.form.get("text")
        topic.title = title
        topic.text = text
        db.add(topic)
        db.commit()
        return redirect(url_for("topic_details", topic_id=topic_id))

@app.route("/topic/<topic_id>/delete", methods=["GET", "POST"])
def topic_delete(topic_id):
    # Check if user is autheticaed based on session_token
    session_token = request.cookies.get("session_token")
    user = db.query(User).filter_by(session_token=session_token).first()

    if not user:
        return redirect(url_for("index"))
    
    topic = db.query(Topic).get(int(topic_id))

    if user.id != topic.author.id:
        return redirect(url_for("index"))
    
    if request.method == "GET":
        return render_template("topic_delete.html", topic=topic, user=user)
    
    elif request.method == "POST":
        db.delete(topic)
        db.commit()
        return redirect(url_for("index"))

if __name__ == "__main__":
    app.run()