import datetime
import os

from flask import Flask, render_template, flash, redirect, jsonify, json, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
import flask_admin
from flask_admin.contrib.sqla import ModelView

from sqlalchemy.orm import Session
from sqlalchemy import MetaData, delete, insert, update, or_, and_
from core import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_DISCOVERY_URL
from model import User

from core import app, db, login_manager, admin
from model import *
from oauthlib.oauth2 import WebApplicationClient
import survey
import compmgr
import requests

###################################################################

# OAuth 2 client setup
client = WebApplicationClient(GOOGLE_CLIENT_ID)
## AUTHENTICATION
@login_manager.unauthorized_handler
def unauthorized():
    return "You must be logged in to access this content.", 403
@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.query(User).get(user_id)
    except:
        return None

###################################################################
## HOME PAGE

# GET /
@app.route('/')
@app.route('/index')
def index():
    '''This is the route for the Home Page.'''
    with app.app_context():
        Base.prepare(autoload_with=db.engine, reflect=True)
    if current_user.is_authenticated:
        return render_template('index.html', title='Genome People')
    else:
        return render_template('login.html', title='Google Login')
@app.route("/login")
def login():
    # Find out what URL to hit for Google login
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    # Use library to construct the request for Google login and provide
    # scopes that let you retrieve user's profile from Google
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=request.base_url + "/callback",
        scope=["openid", "email", "profile"],
    )
    return redirect(request_uri)
@app.route("/login/callback")
def callback():
    with app.app_context():
        Base.prepare(autoload_with=db.engine, reflect=True)
    # Get authorization code Google sent back to you
    code = request.args.get("code")

    # Find out what URL to hit to get tokens that allow you to ask for
    # things on behalf of a user
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]

    
    # Prepare and send request to get tokens! Yay tokens!
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url,
        redirect_url=request.base_url,
        code=code,
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )

    # Parse the tokens!
    client.parse_request_body_response(json.dumps(token_response.json()))

    # Now that we have tokens (yay) let's find and hit URL
    # from Google that gives you user's profile information,
    # including their Google Profile Image and Email
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)

    # We want to make sure their email is verified.
    # The user authenticated with Google, authorized our
    # app, and now we've verified their email through Google!
    if userinfo_response.json().get("email_verified"):
        unique_id = userinfo_response.json()["sub"]
        users_email = userinfo_response.json()["email"]
        picture = userinfo_response.json()["picture"]
        users_name = userinfo_response.json()["given_name"]
    else:
        return "User email not available or not verified by Google.", 400

    # Create a user in our db with the information provided
    # by Google
    user = User(userid=unique_id, loginname=users_name, email=users_email)

    # Doesn't exist? Add to database
    if not db.session.query(User).get(unique_id):
        db.session.add(user)
        db.session.commit()

    # Begin user session by logging the user in
    login_user(user)

    # Send user back to homepage
    return redirect(url_for("index"))
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))

def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()

if __name__ == "__main__":
    app.run(ssl_context="adhoc")
    
###################################################################
## ADMIN ROUTES

class UserModelView(ReadOnlyModelView):
    def is_accessible(self):
        if (current_user.has_roles('admin')):
            return True
        else:
            False
    column_searchable_list = ('email','firstname','lastname')
    column_filters = ('firstname', 'lastname', 'email', 'enabled')
    #can_export = True
    #export_types = ['csv', 'xlsx']

admin.add_view(UserModelView(ModelUser, db.session, category='Users/Roles'))
admin.add_view(ModelView(Role, db.session, category='Users/Roles'))
admin.add_view(ModelView(UserRole, db.session, category='Users/Roles'))

