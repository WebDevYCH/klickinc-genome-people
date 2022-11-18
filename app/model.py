import datetime
import os
import os.path as op
import requests

from flask import Flask, render_template, flash, redirect, jsonify, json, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap
from flask_login import LoginManager
import flask_admin
from flask_admin.contrib.sqla import ModelView

from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import Session
from sqlalchemy import MetaData, delete, insert, update, or_, and_, select

from core import app, db, login_manager

###################################################################
## MODEL

def obj_name(obj):
    return obj.name
def obj_name_withid(obj):
    return f"{obj.name} [{obj.id}]"
def obj_name_user(obj):
    return f"{obj.firstname} {obj.lastname}"
def obj_name_survey_question(obj):
    return f"{obj.survey.name} - {obj.name}"
def obj_name_survey_answer(obj):
    return f"{obj.survey_question.name} - {obj.answer}"

Base = automap_base()
with app.app_context():
    Base.prepare(autoload_with=db.engine, reflect=True)
    session = Session(db.engine)

Base.classes.user.__str__ = obj_name_user
ModelUser = Base.classes.user
class User(ModelUser):
    def is_authenticated(self):
        return self._authenticated
    def has_roles(self, role):
        if (self.employeetypeid==role):
            return True
        else:
            return False
    is_anonymous = False 
    def get_id(self):
        return self.userid
    def is_active(self):
        return self.enabled
    def is_anonymous(self):
        return False

UserRole = Base.classes.user_role
Role = Base.classes.role

CompUser = Base.classes.comp_user

Base.classes.survey.__str__ = obj_name
Survey = Base.classes.survey

Base.classes.survey_question_type.__str__ = obj_name
SurveyQuestionType = Base.classes.survey_question_type

Base.classes.survey_question_category.__str__ = obj_name
SurveyQuestionCategory = Base.classes.survey_question_category

Base.classes.survey_question.__str__ = obj_name_survey_question
SurveyQuestion = Base.classes.survey_question
Base.classes.survey_answer.__str__ = obj_name_survey_answer
SurveyAnswer = Base.classes.survey_answer
SurveyAnswerAnalysis = Base.classes.survey_answer_analysis
SurveyToken = Base.classes.survey_token

# Customized admin interfaces
class ReadOnlyModelView(ModelView):
    can_create = False
    can_edit = False
    can_delete = False 
    can_view_details = True

