import datetime
import os
import os.path as op

from flask import Flask, render_template, flash, redirect, jsonify, json, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap
from flask_login import LoginManager
import flask_admin
from flask_admin.contrib.sqla import ModelView

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField, IntegerField, RadioField, SelectMultipleField, widgets

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
    session = Session(bind=db.engine)

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


@app.route('/survey', methods=['GET', 'POST'])
def survey():
    """Route to the survey."""
    form = SurveyForm()

    query = db.session.query(SurveyQuestion.category.distinct().label("category"))
    categories = [row.category for row in query.all()]

    surveys = db.session.query(Survey).filter(Survey.enabled == "t").all()

    return render_template('survey.html', title='Survey', form=form, surveys=surveys, categories=categories)

@app.route('/save', methods=['POST'])
def save():
    """Route called by Ajax method"""
    ans = SurveyAnswer(survey_id=2)
    for k, v in request.form.items():
        if k.startswith('q'):
            setattr(ans, k, v)
    db.session.add(ans)
    db.session.commit()
    return jsonify({'status': 'ok'})


######################################################################
# Forms

def getQuestions():
    '''Builds list of strs representing in DB defined questions as WTForm-elements.
    (This is some nice and hacky code generation while the program runs.)'''
    questions = session.query(SurveyQuestion).all()
    qslist = []
    for i, q in enumerate(questions):
        choices = generateChoices(q)
        if q.frontend == "StringField":
            qslist.append(
                f'q{(q.id):02} = {q.frontend}("{q.question}", description="{q.category}")')
        elif q.frontend == "RadioField":
            qslist.append(
                f'q{(q.id):02} = {q.frontend}("{q.question}", choices={repr(choices)}, description="{q.category}")')
        elif q.frontend == "SelectField":
            qslist.append(
                f'q{(q.id):02} = {q.frontend}("{q.question}", choices={repr(choices)}, description="{q.category}")')
        elif q.frontend == "SelectMultipleField" or "MultiCheckboxField":
            qslist.append(
                f'q{(q.id):02} = {q.frontend}("{q.question}", choices={repr(choices)}, option_widget=widgets.CheckboxInput(), description="{q.category}")')
    return qslist


def generateChoices(q):
    '''Generates list of tuples from answer choices to a given question.'''
    items = q.__dict__.items()
    l = [(k, v) for k, v in items if k.startswith(
        "ans") and v != '' and v != None]
    l.sort()
    return l

class SurveyForm(FlaskForm):
    """The final survey form. Generated on the fly from questions in the DB."""
    qslist = getQuestions()
    
    for qs in qslist:
        exec(qs)
    submit = SubmitField('Send')


