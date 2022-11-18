import datetime
import requests

from flask import Flask, render_template, flash, redirect, jsonify, json, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap
from flask_login import LoginManager, current_user
import flask_admin
from flask_admin.contrib.sqla import ModelView

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField, IntegerField, RadioField, SelectMultipleField, TextAreaField, widgets

from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import Session
from sqlalchemy import MetaData, delete, insert, update, or_, and_

from google.cloud import language_v1

from core import app, db, login_manager, admin
from model import Base, session, ReadOnlyModelView, \
    CompUser

###################################################################
## COMP MGR

class CompUserView(ModelView):
    def is_accessible(self):
        if (current_user.has_roles('admin')):
            return True
        else:
            False
    can_export = True
    export_types = ['csv', 'xlsx']
admin.add_view(CompUserView(CompUser, db.session, category='Comp Mgr'))


