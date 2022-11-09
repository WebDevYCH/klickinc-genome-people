import datetime
import os
import os.path as op

from flask import Flask, render_template, flash, redirect, jsonify, json, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap
from flask_login import LoginManager
import flask_admin
from flask_admin.contrib.sqla import ModelView

from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import Session
from sqlalchemy import MetaData

import config

###################################################################
## INITIALIZATION

# Create application reference
app = config.configapp(Flask(__name__))
Bootstrap(app)
login_manager = LoginManager()
login_manager.init_app(app)

# Create db reference
db = SQLAlchemy(app)
db.init_app(app)

###################################################################
## MODEL

Base = automap_base()
with app.app_context():
    Base.prepare(db.engine, reflect=True)

ModelUser = Base.classes.user
class User(ModelUser):
    is_authenticated = False 
    is_active = False 
    is_anonymous = False 
    def get_id():
        return userid

UserRole = Base.classes.user_role
Role = Base.classes.role
Survey = Base.classes.survey
SurveyQuestionType = Base.classes.survey_question_type
SurveyQuestion = Base.classes.survey_question
SurveyAnswer = Base.classes.survey_answer
SurveyToken = Base.classes.survey_token

# Customized admin interfaces
class ReadOnlyModelView(ModelView):
    can_create = False
    can_edit = False
    can_delete = False 
class UserAdmin(ReadOnlyModelView):
    column_searchable_list = ('email','firstname','lastname')
    column_filters = ('firstname', 'lastname', 'email', 'enabled')
    can_export = True
    export_types = ['csv', 'xlsx']
    can_view_details = True

###################################################################
## AUTHENTICATION

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

###################################################################
## ADMIN ROUTES

# GET /
@app.route('/')
@app.route('/index')
def index():
    '''This is the route for the Home Page.'''
    return render_template('index.html', title='Genome People')


# GET /admin/
# Create admin with custom base template
admin = flask_admin.Admin(app, 'Genome People Admin', template_mode='bootstrap4')
# Add views for CRUD
admin.add_view(UserAdmin(ModelUser, db.session, category='Menu'))
admin.add_view(ModelView(Role, db.session, category='Menu'))
admin.add_view(ModelView(UserRole, db.session, category='Menu'))
admin.add_view(ModelView(Survey, db.session, category='Menu'))
admin.add_view(ModelView(SurveyQuestionType, db.session, category='Menu'))
admin.add_view(ModelView(SurveyQuestion, db.session, category='Menu'))
admin.add_view(ModelView(SurveyAnswer, db.session, category='Menu'))

###################################################################
## SURVEY ROUTES




