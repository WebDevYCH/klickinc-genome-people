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
from sqlalchemy import delete, insert, update, or_, and_, select

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.automap import automap_base

from core import app, db, login_manager

###################################################################
## MODEL

def obj_name(obj):
    return obj.name
def obj_title(obj):
    return obj.title
def obj_name_withid(obj):
    return f"{obj.name} [{obj.id}]"
def obj_name_user(obj):
    return f"{obj.firstname} {obj.lastname}"
def obj_name_survey_question(obj):
    return f"{obj.survey.name} - {obj.name}"
def obj_name_survey_answer(obj):
    return f"{obj.survey_question.name} - {obj.answer}"
def obj_name_joined(obj):
    return ['id', 'job_or_availadble', 'job_posting_category_id', 'poster_user_id', 'posted_date', 'expiry_date', 'removed_date', 'title', 'description', 'contact_user_id', 'name']

# Connect directly to database to make the schema, outside of the Flask context so we can
# initialize before the first web request
dbengine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
Session = sessionmaker(bind=dbengine)
dbsession = Session()

dbmetadata = MetaData()
dbmetadata.reflect(dbengine)
Base = automap_base(metadata=dbmetadata)
Base.prepare()

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

# Job Ads
Base.classes.job_posting.__str__ = obj_name
Base.classes.job_posting.__json__ = obj_name_joined
JobPosting = Base.classes.job_posting

Base.classes.job_posting_category.__str__ = obj_name
JobPostingCategory = Base.classes.job_posting_category

JobPostingSkill = Base.classes.job_posting_skill

# Skills
Base.classes.skill.__str__ = obj_name
Skill = Base.classes.skill

Base.classes.user_skill_source.__str__ = obj_name
UserSkillSource = Base.classes.user_skill_source

UserSkill = Base.classes.user_skill

Base.classes.title.__str__ = obj_name
Title = Base.classes.title

TitleSkill = Base.classes.title_skill

Base.classes.labor_role.__str__ = obj_name
LaborRole = Base.classes.labor_role

LaborRoleSkill = Base.classes.labor_role_skill

# profile
UserProfile = Base.classes.user_profile

# Portfolios etc.
Base.classes.portfolio.__str__ = obj_name
Portfolio = Base.classes.portfolio

PortfolioForecast = Base.classes.portfolio_forecast

PortfolioLRForecast = Base.classes.portfolio_laborrole_forecast



