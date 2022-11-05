import datetime
import os
import os.path as op

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import flask_admin as admin
from flask_admin.contrib.sqla import ModelView

from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import Session
from sqlalchemy import MetaData

import config

## INITIALIZATION
# Create application and db references
app = config.configapp(Flask(__name__))
db = SQLAlchemy(app)

## MODEL
db.init_app(app)
Base = automap_base()
with app.app_context():
    Base.prepare(db.engine, reflect=True)


# Models
#Users = Base.classes.user
class User(db.Model):
    __tablename__ = 'user'
    userid = db.Column(db.Integer, primary_key=True)
    loginname = db.Column(db.String(64), unique=True)
    firstname = db.Column(db.String(64))
    lastname = db.Column(db.String(64))
    email = db.Column(db.String(64))
    title = db.Column(db.String(64))
    enabled = db.Column(db.Boolean)
    supervisoruserid = db.Column(db.Integer)

UserRole = Base.classes.user_roles
Role = Base.classes.roles
SurveyQuestion = Base.classes.survey_questions
SurveyAnswer = Base.classes.survey_answers
SurveyToken = Base.classes.survey_tokens


# Customized admin interface
class CustomView(ModelView):
    pass

class UserAdmin(CustomView):
    column_searchable_list = ('email',)
    column_filters = ('firstname', 'lastname', 'email')
    can_export = True
    export_types = ['csv', 'xlsx']



## ROUTES

# GET /
@app.route('/')
def index():
    return '<a href="/admin/">Click me to get to Admin!</a>'

# GET /admin/
# Create admin with custom base template
admin = admin.Admin(app, 'Example: Bootstrap4', template_mode='bootstrap4')

# Add views for CRUD
admin.add_view(UserAdmin(User, db.session, category='Menu'))
admin.add_view(CustomView(Role, db.session, category='Menu'))
admin.add_view(CustomView(UserRole, db.session, category='Menu'))
admin.add_view(CustomView(SurveyQuestion, db.session, category='Menu'))
admin.add_view(CustomView(SurveyAnswer, db.session, category='Menu'))

