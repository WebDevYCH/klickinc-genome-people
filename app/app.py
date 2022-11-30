import datetime
import os

from flask import Flask, render_template, flash, redirect, jsonify, json, url_for, request
from flask_bootstrap import Bootstrap
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from flask_admin.menu import MenuCategory, MenuView, MenuLink, SubMenuCategory
import flask_admin

import sqlalchemy
from sqlalchemy import delete, insert, update, or_, and_

from core import *
from model import *

from oauthlib.oauth2 import WebApplicationClient
import survey
import compmgr
import requests
import dbreplication

###################################################################
## HOME PAGE

# GET /
@app.route('/')
@app.route('/index')
def index():
    '''This is the route for the Home Page.'''
    if current_user.is_authenticated:
        return render_template('index.html', title='Genome People')
    else:
        #return render_template('login.html', title='Google Login') # webpage with login button
        return redirect("/login") # redirect straight to the oath process


###################################################################
## STATIC PATHS (maps /css/x.css to /static/css/x.css, for e.g.)

@app.route('/css/<path:text>')
@app.route('/fonts/<path:text>')
@app.route('/img/<path:text>')
@app.route('/js/<path:text>')
def static_file(text):
    return app.send_static_file(request.path[1:])


###################################################################
## AUTHENTICATION / LOGIN

# GET /login
@app.route("/login")
def login():
    # Find out what URL to hit for Google login
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    login_next = request.args.get('next')
    if login_next:
        session['login_next'] = login_next

    # Use library to construct the request for Google login and provide
    # scopes that let you retrieve user's profile from Google
    request_uri = oathclient.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=request.base_url + "/callback",
        scope=["openid", "email", "profile"],
    )
    return redirect(request_uri)

# GET /login/callback
@app.route("/login/callback")
def callback():
    # Get authorization code Google sent back to you
    code = request.args.get("code")

    # Find out what URL to hit to get tokens that allow you to ask for
    # things on behalf of a user
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]
    
    # Prepare and send request to get tokens! Yay tokens!
    token_url, headers, body = oathclient.prepare_token_request(
        token_endpoint,
        authorization_response=request.url,
        redirect_url=request.base_url,
        code=code,
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(app.config['GOOGLE_CLIENT_ID'], app.config['GOOGLE_CLIENT_SECRET']),
    )

    # Parse the tokens!
    oathclient.parse_request_body_response(json.dumps(token_response.json()))

    # Now that we have tokens (yay) let's find and hit URL
    # from Google that gives you user's profile information,
    # including their Google Profile Image and Email
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = oathclient.add_token(userinfo_endpoint)
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

    try:
        user = db.session.query(User).filter(User.email==users_email).first()
    except sqlalchemy.orm.exc.UnmappedClassError:
        # if the autoloaded model isn't initialized yet, then initialize
        with app.app_context():
            Base.prepare(autoload_with=db.engine, reflect=True)
        # ...and then retry the query
        user = db.session.query(User).filter(User.email==users_email).first()

    if user:
        login_user(user)
        if 'login_next' in session:
            return redirect(session.pop('login_next'))
        else:
            return redirect(url_for("index"))
    else:
        return "You are not in the user list and are not authorized to use this application.", 400

# GET /logout
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))

# OAuth 2 client setup
oathclient = WebApplicationClient(app.config["GOOGLE_CLIENT_ID"])
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
if __name__ == "__main__":
    app.run(ssl_context="adhoc")

## AUTHENTICATION
login_manager.login_view = "login"
@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.query(User).get(user_id)
    except sqlalchemy.orm.exc.UnmappedClassError:
        # if the autoloaded model isn't initialized yet, then initialize
        with app.app_context():
            Base.prepare(autoload_with=db.engine, reflect=True)
        # ...and then retry the query
        return db.session.query(User).get(user_id)

def get_google_provider_cfg():
    return requests.get(app.config['GOOGLE_DISCOVERY_URL']).json()

###################################################################
## ADMIN ROUTES

class UserModelView(ReadOnlyModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.has_roles('user_admin')
    column_searchable_list = ('email','firstname','lastname')
    column_filters = ('firstname', 'lastname', 'email', 'enabled')

admin.add_link(MenuLink(name='Frontend', url='/'))
admin.add_link(MenuLink(name='Logout', url='/logout'))

admin.add_view(UserModelView(ModelUser, db.session, category='Users/Roles'))
admin.add_view(AdminModelView(Role, db.session, category='Users/Roles'))
admin.add_view(AdminModelView(UserRole, db.session, category='Users/Roles'))

