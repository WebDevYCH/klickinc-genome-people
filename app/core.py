import datetime
import os
import os.path as op
import requests

from flask import Flask, render_template, flash, redirect, jsonify, json, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_admin.contrib.sqla import ModelView
from flask_admin.menu import MenuCategory, MenuView, MenuLink, SubMenuCategory
from flask_bootstrap import Bootstrap
from flask_login import LoginManager, current_user
import flask_admin
import config

###################################################################
## INITIALIZATION

# Create application reference
app = config.configapp(Flask(__name__))
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)
Bootstrap(app)

# login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.session_protection = 'strong'

# Create db reference
db = SQLAlchemy(app)
db.init_app(app)

# Flask-Admin interfaces
class MyAdminIndexView(flask_admin.AdminIndexView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.has_roles('admin')
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login', next=request.url))

admin = flask_admin.Admin(app, 'Genome People Admin', template_mode='bootstrap4', index_view=MyAdminIndexView())

# Customized admin/crud interfaces ensure there's at least basic authentication and permissions
class AdminModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.has_roles('admin')
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login', next=request.url))
 
class ReadOnlyModelView(AdminModelView):
    can_create = False
    can_edit = False
    can_delete = False 
    can_view_details = True

