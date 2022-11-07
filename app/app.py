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
User = Base.classes.user
UserRole = Base.classes.user_role
Role = Base.classes.role
Survey = Base.classes.survey
SurveyQuestion = Base.classes.survey_question
SurveyAnswer = Base.classes.survey_answer
SurveyToken = Base.classes.survey_token

# Customized admin interfaces
class UserAdmin(ModelView):
    column_searchable_list = ('email','firstname','lastname')
    column_filters = ('firstname', 'lastname', 'email', 'enabled')
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
admin.add_view(ModelView(Role, db.session, category='Menu'))
admin.add_view(ModelView(UserRole, db.session, category='Menu'))
admin.add_view(ModelView(Survey, db.session, category='Menu'))
admin.add_view(ModelView(SurveyQuestion, db.session, category='Menu'))
admin.add_view(ModelView(SurveyAnswer, db.session, category='Menu'))

