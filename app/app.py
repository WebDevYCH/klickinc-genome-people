import datetime
import os
import os.path as op
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

import flask_admin as admin
from flask_admin.contrib.sqla import ModelView

from model import *

## ROUTES

# GET /
@app.route('/')
def index():
    return '<a href="/admin/">Click me to get to Admin!</a>'


# GET /admin/
# Create admin with custom base template
admin = admin.Admin(app, 'Example: Bootstrap4', template_mode='bootstrap4')

# Add views for CRUD
admin.add_view(UserAdmin(Users, db.session, category='Menu'))
admin.add_view(CustomView(Roles, db.session, category='Menu'))
admin.add_view(CustomView(UserRoles, db.session, category='Menu'))
admin.add_view(CustomView(SurveyQuestions, db.session, category='Menu'))
admin.add_view(CustomView(SurveyAnswers, db.session, category='Menu'))

