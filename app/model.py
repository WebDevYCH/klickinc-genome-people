import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_admin.contrib.sqla import ModelView
from flask import Flask

from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import Session
from sqlalchemy import create_engine

import config

Base = automap_base()
modelengine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
Base.prepare(engine, reflect=True, schema=app.config['DATABASE'])

# Models
# users
Users = Base.classes.user
UserRoles = Base.classes.user_roles
Roles = Base.classes.roles
SurveyQuestions = Base.classes.survey_questions
SurveyAnswers = Base.classes.survey_answers
SurveyTokens = Base.classes.survey_tokens


# Customized admin interface
class CustomView(ModelView):
	pass

class UserAdmin(CustomView):
	column_searchable_list = ('email',)
	column_filters = ('firstname', 'lastname', 'email')
	can_export = True
	export_types = ['csv', 'xlsx']


