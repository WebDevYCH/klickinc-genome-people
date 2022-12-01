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
from sqlalchemy.exc import IntegrityError

from core import *
from model import *

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Route to the job."""
    form = ProfileForm()
    profile = db.session.query(UserProfile).filter(UserProfile.user_id==current_user.userid).one()
    skillform = SkillForm()
    lightcast_response = get_allskills_from_lightcast()
    print(lightcast_response)
    if form.validate_on_submit():
        if profile:
            profile.resume = form.resume.data
            db.session.commit()
            flash("Successfully updated your resume!")
        else:
            user_profile = UserProfile(resume=form.resume.data, user_id=int(current_user.userid))
            db.session.add(user_profile)
            db.session.commit()
            flash("Successfully added your resume")
    if skillform.validate_on_submit():
        skill = db.session.query(UserSkill).query(UserSkill.user)
    return render_template('profile/index.html', form=form, skillform=skillform, profile=profile, user=current_user)

def get_lightcast_auth_token():
    url = "https://auth.emsicloud.com/connect/token"
    payload = "client_id=" + app.config['LIGHTCAST_API_CLIENTID'] + "&client_secret=" + app.config['LIGHTCAST_API_SECRET'] + "&grant_type=client_credentials&scope=emsi_open"
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}

    response = requests.request("POST", url, data=payload, headers=headers)

    return response.json()['access_token']

def get_allskills_from_lightcast():
    url = "https://emsiservices.com/skills/versions/latest/skills"

    querystring = {"q":".NET","typeIds":"ST1,ST2","fields":"id,name,type,infoUrl","limit":"5"}

    bearer_token = 'Bearer' + get_lightcast_auth_token()
    headers = {'Authorization': bearer_token}

    response = requests.request("GET", url, headers=headers, params=querystring)

    return response.json()

class ProfileForm(FlaskForm):
    resume = TextAreaField('description', validators=[InputRequired()])

class SkillForm(FlaskForm):
    skillid = SelectField('skillid', choices=[])

    def __init__(self, *args, **kwargs):
        super(SkillForm, self).__init__(*args, **kwargs)
        SKILL_CHOICES = []
        skills = db.session.query(Skill).all()
        for x in skills:
            SKILL_CHOICES.append((x.id, x.name))
        self.skillid.choices = SKILL_CHOICES
