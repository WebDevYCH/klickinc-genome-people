import datetime
import requests

from flask import Flask, render_template, flash, redirect, jsonify, json, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap
from flask_login import LoginManager, login_required, current_user
from flask_admin import expose
from flask_admin.menu import MenuCategory, MenuView, MenuLink, SubMenuCategory

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField, IntegerField, RadioField, SelectMultipleField, TextAreaField, widgets
from wtforms.validators import InputRequired, Length
from sqlalchemy.ext.automap import automap_base
from sqlalchemy import MetaData, delete, insert, update, or_, and_

from google.cloud import language_v1

from core import *
from model import *

admin.add_view(AdminModelView(LaborRoleSkill, db.session, category='Skill'))
admin.add_view(AdminModelView(TitleSkill, db.session, category='Skill'))
admin.add_view(AdminModelView(Skill, db.session, category='Skill'))
