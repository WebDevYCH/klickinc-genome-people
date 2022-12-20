import datetime
import os, time
import requests

from flask import Flask, redirect, url_for, request
from flask_sqlalchemy import SQLAlchemy
import flask_admin
from flask_admin.contrib.sqla import ModelView
from flask_bootstrap import Bootstrap
from flask_login import LoginManager, current_user
from flask_crontab import Crontab
import config
import gspread

###################################################################
## INITIALIZATION

# Create application reference
app = config.configapp(Flask(__name__))
app.secret_key = app.config['SECRET_KEY'] or os.urandom(24)
Bootstrap(app)
crontab = Crontab(app)

# login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.session_protection = 'strong'

# Create db reference
db = SQLAlchemy(app)
db.init_app(app)

# filter out some sqlalchemy warnings
import warnings
from sqlalchemy import exc as sa_exc
warnings.filterwarnings("ignore", category=sa_exc.SAWarning)

###################################################################
## ADMIN CLASSES

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

###################################################################
## UTILITY CLASSES AND FUNCTIONS

# overridden array that saves in the array and also logs to the webapp logfile
class AdminLog(list):
    def append(self, item):
        app.logger.info(item)
        super().append(item)

# class to do basic in-memory caching of data
cache_cache = {}
class Cache:
    def __init__(self):
        cache_cache = {}
    def get(key):
        if key in cache_cache:
            if cache_cache[key]['timeout'] == 0 or cache_cache[key]['time'] + cache_cache[key]['timeout'] > time.time():
                return cache_cache[key]['value']
            else:
                del cache_cache[key]
        return None
    def set(key, value, timeout=0):
        cache_cache[key] = {'value': value, 'timeout': timeout, 'time': time.time()}


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

def getGoogleSheet(url):
    #scope = ['https://spreadsheets.google.com/feeds']
    #credentials = ServiceAccountCredentials.from_json_keyfile_name(app.config['GOOGLE_CREDENTIALS'], scope)
    #gc = gspread.authorize(credentials)
    #return gc.open_by_url(url)
    gc = gspread.service_account(filename = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'))
    return gc.open_by_url(url)

# set the format of a cell in a google sheet, but retry for up to a minute if it hits a rate limit
def setGoogleSheetCellFormat(worksheet, cellpos, format):
    for i in range(0, 60):
        try:
            worksheet.format(cellpos, format)
            return
        except gspread.exceptions.APIError as e:
            if e.response.status_code == 429:
                time.sleep(1)
            else:
                raise e

