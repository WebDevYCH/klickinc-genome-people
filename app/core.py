import datetime
import os
import os.path as op
import requests

from flask import Flask, render_template, flash, redirect, jsonify, json, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap
from flask_login import LoginManager, current_user
import flask_admin
import config

# Configuration for Google authentication
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)  #set GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)  #set GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_DISCOVERY_URL = (
    "https://accounts.google.com/.well-known/openid-configuration"
)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
###################################################################
## INITIALIZATION

# Create application reference
app = config.configapp(Flask(__name__))
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)
Bootstrap(app)

# login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.session_protection = 'strong'

# Create db reference
db = SQLAlchemy(app)
db.init_app(app)

# Flask-Admin interfaces
class MyAdminIndexView(flask_admin.AdminIndexView):
    def is_accessiblexx(self):
        return current_user.is_authenticated()
admin = flask_admin.Admin(app, 'Genome People Admin', template_mode='bootstrap4', index_view=MyAdminIndexView())
