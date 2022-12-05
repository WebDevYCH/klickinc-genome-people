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

#admin.add_view(AdminModelView(JobPosting, db.session, category='Jobs/Postings'))
#admin.add_view(AdminModelView(JobPostingCategory, db.session, category='Jobs/Postings'))
#admin.add_view(AdminModelView(JobPostingSkill, db.session, category='Jobs/Postings'))


@app.route('/job/jobs', methods=['GET', 'POST'])
@login_required
def job():
    """Route to the job."""
    # form = JobForm()

    jobs = db.session.query(JobPosting).all()

    return render_template('job/index.html', title='Jobs', jobs=jobs)

@app.route('/job/jobs-create', methods=['GET', 'POST'])
@login_required
def create():

    form = JobForm()

    return render_template('job/create.html', title='Job create', form=form)

class JobForm(FlaskForm):
    title = StringField('title', validators=[InputRequired(), Length(min=10, max=200)])
    description = TextAreaField('description', validators=[InputRequired(), Length(max=250)])
    jobOrAvailable = BooleanField('job_or_available', default='checked')
    submit = SubmitField('Send')
