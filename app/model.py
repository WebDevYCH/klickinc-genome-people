import datetime
import os
import os.path as op
import requests

from flask import Flask, render_template, flash, redirect, jsonify, json, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap
from flask_login import LoginManager,UserMixin
import flask_admin

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
UserRole = Base.classes.user_role
Base.classes.role.__str__ = obj_name
Role = Base.classes.role
class User(ModelUser):
    def has_roles(self, rolename):
        for roles in db.session.query(Role).join(UserRole).\
            where(UserRole.user_id==self.userid,Role.name==rolename).all():
            return True
        return False
    def is_authenticated(self):
        return True
    def is_active(self):
        return self.enabled
    def is_anonymous(self):
        return False
    def get_id(self):
        return str(self.userid)

# Compensation Manager
CompMgr = Base.classes.comp_mgr

# Survey
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

