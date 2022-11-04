import datetime
import os
import os.path as op
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

import flask_admin as admin
from flask_admin.contrib.sqla import ModelView

from model import *

# Create application
app = Flask(__name__)

# Create dummy secrey key so we can use sessions
app.config['SECRET_KEY'] = '123456790'
app.config['FLASK_ADMIN_SWATCH'] = 'flatly'
#app.config['FLASK_ADMIN_SWATCH'] = 'Minty'

# Create in-memory database
app.config['DATABASE_FILE'] = 'sample_db.sqlite'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + app.config['DATABASE_FILE']
app.config['SQLALCHEMY_ECHO'] = True

db = SQLAlchemy(app)

# Flask views
@app.route('/')
def index():
    return '<a href="/admin/">Click me to get to Admin!</a>'


# Create admin with custom base template
admin = admin.Admin(app, 'Example: Bootstrap4', template_mode='bootstrap4')

# Add views
admin.add_view(UserAdmin(User, db.session, category='Menu'))
admin.add_view(CustomView(Page, db.session, category='Menu'))

