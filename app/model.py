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

# profile
UserProfile = Base.classes.user_profile

Base.classes.labor_role.__str__ = obj_name
LaborRole = Base.classes.labor_role



