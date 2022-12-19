import datetime
import os
import os.path as op
import requests

from flask import Flask, render_template, flash, redirect, jsonify, json, url_for, request, session
from flask_sqlalchemy import SQLAlchemy
import flask_admin
from flask_admin.contrib.sqla import ModelView
from flask_bootstrap import Bootstrap
from flask_login import LoginManager, current_user
import config

###################################################################
## INITIALIZATION

# Create application reference
app = config.configapp(Flask(__name__))
app.secret_key = app.config['SECRET_KEY'] or os.urandom(24)
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
    def is_accessible(self):
        return current_user.is_authenticated and current_user.has_roles('admin')
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login', next=request.url))

admin = flask_admin.Admin(app, 'Genome People Admin', template_mode='bootstrap4', index_view=MyAdminIndexView())

# Customized admin/crud interfaces ensure there's at least basic authentication and permissions
class AdminModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.has_roles('admin')
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login', next=request.url))
 
class ReadOnlyModelView(AdminModelView):
    can_create = False
    can_edit = False
    can_delete = False 
    can_view_details = True

class AdminBaseView(flask_admin.BaseView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.has_roles('admin')
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login', next=request.url))

# overridden array that saves in the array and also logs to the webapp logfile
class AdminLog(list):
    def append(self, item):
        app.logger.info(item)
        super().append(item)

# function used in a bunch of places to pick up data from Genome
def retrieveGenomeReport(queryid, tokenids=[], tokenvalues=[]):
    apikey = app.config['GENOME_API_TOKEN']
    apiendpoint = f"{app.config['GENOME_API_ROOT']}/QueryTemplate/Report?_={apikey}"
    reqjson = {
        'QueryTemplateID': queryid,
        'TokenIDs': tokenids,
        'TokenValues': tokenvalues
    }

    app.logger.info(f"GENOME QUERY JSON {reqjson}")
    response = requests.post(apiendpoint, json=reqjson)
    return response.json()

def parseGenomeDate(weirdstring):
    # date comes back in the format '/Date(1262322000000-0500)/', ie milliseconds since 1970-01-01
    return datetime.datetime.fromtimestamp(int(weirdstring[6:16]))



