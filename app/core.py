from asyncio import sleep
import datetime
import os, time
import re
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
import openai

###################################################################
## INITIALIZATION

# Create application reference
app = config.configapp(Flask(__name__))
app.secret_key = app.config['SECRET_KEY'] or os.urandom(24)
Bootstrap(app)
crontab = Crontab(app)
while app.logger.handlers:
    # something is adding an extra handler, which causes duplicate log messages
    app.logger.handlers.pop()

# login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.session_protection = 'strong'

# Create db reference
app.logger.info("Initializing database")
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

# upsert function (since it doesn't exist in sqlalchemy)
def upsert(session, model, constraints, values, usecache=False):
    """
    Perform an upsert operation using SQLAlchemy.

    :param session: A SQLAlchemy session object
    :param model: The model representing the table to update
    :param constraints: A dictionary representing the unique constraints
    :param values: A dictionary representing the values to set
    :return: bool, True if the row was inserted or updated
    """
    retval = False
    # first see if we have a cache of this object and constraints to avoid queries, otherwise do a query
    if usecache:
        constraintkeys = list(constraints.keys())
        constraintkeys.sort()
        outercachekey = f"upsert-cache-{model.__name__}-{','.join(constraintkeys)}"
        cache = Cache.get(outercachekey)
        if not cache:
            cache = {}
            app.logger.info(f"** CACHE MISS, creating new full table cache for {outercachekey}")
            for cobj in session.query(model).all():
                innercachekey = ','.join([f"{k}:{getattr(cobj, k)}" for k in constraintkeys])
                #app.logger.info(f"** adding object to cache for cachekey {innercachekey}")
                cache[innercachekey] = cobj
            Cache.set(outercachekey, cache)


    # now get the object if we don't have it
    obj = None
    if usecache:
        # inner cache key should be a string of the key-value pairs in the constraints
        innercachekey = ','.join([f"{k}:{constraints[k]}" for k in constraintkeys])
        obj = cache.get(innercachekey)
        innercachekey = ','.join([f"{k}:{constraints[k]}" for k in constraintkeys])
        if not obj:
            app.logger.info(f"** cache miss (how did this happen??), querying for object for cachekey {innercachekey}")
            query = session.query(model).filter_by(**constraints)
            obj = query.first()
            cache[innercachekey] = obj
    else:
        query = session.query(model).filter_by(**constraints)
        obj = query.first()

    if obj:
        # Update existing object
        for key, value in values.items():
            if getattr(obj, key) == value:
                pass
            else:
                # TODO: figure out why it keeps updating fields that haven't changed
                setattr(obj, key, value)
                #app.logger.info(f"** updating {model.__name__}.{key}: {getattr(obj,key)} != {value}; the types are {type(getattr(obj,key))} and {type(value)}")
                retval = True
    else:
        # Create new object
        obj = model(**constraints, **values)
        session.add(obj)
        retval = True
        if usecache:
            innercachekey = ','.join([f"{k}:{constraints[k]}" for k in constraintkeys])
            cache[innercachekey] = obj

    return retval

###################################################################
## OPENAI FUNCTIONS

def gpt3_embedding(content, engine='text-embedding-ada-002'):
    content = content.encode(encoding='ASCII',errors='ignore').decode()
    response = openai.Embedding.create(input=content,engine=engine)
    vector = response['data'][0]['embedding']  # this is a normal list
    return vector

def gpt3_completion(prompt, engine='text-davinci-003', temp=0.0, top_p=1.0, tokens=400, freq_pen=0.0, pres_pen=0.0, stop=None):
    max_retry = 5
    retry = 0
    prompt = prompt.encode(encoding='ASCII',errors='ignore').decode()
    while True:
        try:
            response = openai.Completion.create(
                engine=engine,
                prompt=prompt,
                temperature=temp,
                max_tokens=tokens,
                top_p=top_p,
                frequency_penalty=freq_pen,
                presence_penalty=pres_pen,
                stop=stop)
            text = response['choices'][0]['text'].strip()
            text = re.sub('[\r\n]+', '\n', text)
            text = re.sub('[\t ]+', '  ', text)
            return text
        except Exception as oops:
            retry += 1
            if retry >= max_retry:
                return "GPT3 error: %s" % oops
            app.logger.error('Error communicating with OpenAI: %s', oops)
            sleep(1)


