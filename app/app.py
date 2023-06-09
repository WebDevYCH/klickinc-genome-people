import os

from flask import render_template, redirect, json, url_for, request, session
from flask_login import current_user, login_required, login_user, logout_user
from flask_admin.menu import MenuLink

import sqlalchemy

from core import *
from model import *

# don't trim out these imports -- they carry the routes
import compmgr
import dbreplication
import forecasts_fe
import forecasts_charts
import forecasts_be
import tmkt_fe
import tmkt_be
import profile_fe as profile_fe
import skills
import survey
import chat


from oauthlib.oauth2 import WebApplicationClient
import requests

###################################################################
## HOME PAGE

# GET /
@app.route('/')
@app.route('/index')
def mainindex():
    # every URL should be under /p
    return redirect("/p/")


# GET /p
@app.route('/p')
@app.route('/p/')
def index():
    '''This is the route for the Home Page.'''
    if current_user.is_authenticated:
        return render_template('index.html', title='Main')
    else:
        #return render_template('login.html', title='Google Login') # webpage with login button
        return redirect("/p/login") # redirect straight to the oath process


###################################################################
## STATIC PATHS (maps /css/x.css to /static/css/x.css, for e.g.)

@app.route('/p/css/<path:text>')
@app.route('/p/static/css/<path:text>')
@app.route('/p/fonts/<path:text>')
@app.route('/p/static/fonts/<path:text>')
@app.route('/p/img/<path:text>')
@app.route('/p/static/img/<path:text>')
@app.route('/p/js/<path:text>')
@app.route('/p/static/js/<path:text>')
def static_file(text):
    filename = request.path[3:].replace('static/','')
    return app.send_static_file(filename)


###################################################################
## AUTHENTICATION / LOGIN

# GET /p/login
@app.route("/p/login")
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

# GET /p/login/callback
@app.route("/p/login/callback")
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

# GET /p/logout
@app.route("/p/logout")
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

admin.add_link(MenuLink(name='Frontend', url='/p/'))
admin.add_link(MenuLink(name='Logout', url='/p/logout'))

admin.add_view(UserModelView(ModelUser, db.session, category='Users/Roles'))
admin.add_view(AdminModelView(Role, db.session, category='Users/Roles'))

class UserRoleModelView(AdminModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.has_roles('user_admin')
    column_searchable_list = ('user.firstname','user.lastname','role.name')
    column_sortable_list = ('user.firstname','user.lastname','role.name')
    #column_filters = ('role')
    #column_editable_list = ('role')

admin.add_view(UserRoleModelView(UserRole, db.session, category='Users/Roles'))

