import datetime
import os

from flask import Flask, render_template, flash, redirect, jsonify, json, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap
from flask_login import LoginManager
import flask_admin
from flask_admin.contrib.sqla import ModelView

from sqlalchemy.orm import Session
from sqlalchemy import MetaData, delete, insert, update, or_, and_

from core import app, db, login_manager, admin
from model import Base, session, ReadOnlyModelView, ModelUser, UserRole, Role
import survey
import compmgr

###################################################################
## AUTHENTICATION

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

###################################################################
## HOME PAGE

# GET /
@app.route('/')
@app.route('/index')
def index():
    '''This is the route for the Home Page.'''
    return render_template('index.html', title='Genome People')

###################################################################
## ADMIN ROUTES

class UserModelView(ReadOnlyModelView):
    column_searchable_list = ('email','firstname','lastname')
    column_filters = ('firstname', 'lastname', 'email', 'enabled')
    #can_export = True
    #export_types = ['csv', 'xlsx']

admin.add_view(UserModelView(ModelUser, db.session, category='Users/Roles'))
admin.add_view(ModelView(Role, db.session, category='Users/Roles'))
admin.add_view(ModelView(UserRole, db.session, category='Users/Roles'))

