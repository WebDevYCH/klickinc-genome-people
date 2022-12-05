from flask import render_template, flash, redirect, url_for
from flask_login import login_required, current_user

from flask_wtf import FlaskForm
from wtforms import SelectField, TextAreaField, SelectMultipleField
from wtforms.validators import InputRequired

from core import *
from model import *
from helpers import *

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Route to the job."""
    form = ProfileForm()
    profile = db.session.query(UserProfile).filter(UserProfile.user_id==current_user.userid).first()
    my_skills = db.session.query(Skill).join(UserSkill).where(UserSkill.user_id == current_user.userid).all()
    skillform = SkillForm()
    # fill_skills_by_lightcast_api()
    if form.validate_on_submit():
        if profile:
            relevant_skills = extract_skills_from_text(form.resume.data)
            auto_fill_user_skill_from_resume(relevant_skills)
            profile.resume = form.resume.data
            db.session.commit()
            flash("Successfully updated!")
        else:
            user_profile = UserProfile(resume=form.resume.data, user_id=int(current_user.userid))
            db.session.add(user_profile)
            db.session.commit()
            flash("Successfully added your resume")
    return render_template('profile/index.html', form=form, skillform=skillform, profile=profile, user=current_user, skills=my_skills)

@app.route('/skill-edit', methods=['GET', 'POST'])
@login_required
def skill_edit():
    skillform = SkillForm()
    my_skills = db.session.query(Skill).join(UserSkill).where(UserSkill.user_id == current_user.userid).all()
    return render_template('profile/skill_edit.html', skillform=skillform, skills=my_skills)

@app.route('/skill-add', methods=['POST'])
@login_required
def skill_add():
    skillform = SkillForm()
    if skillform.validate_on_submit():
        for id in skillform.skillid.data:
            if not db.session.query(UserSkill).filter(UserSkill.user_id==current_user.userid, UserSkill.skill_id==id).first():
                new_skill = UserSkill(skill_id=id, user_id=int(current_user.userid), user_skill_source_id=1)
                db.session.add(new_skill)
        db.session.commit()
        flash("Successfully added your skills!") 
    return redirect(url_for('skill_edit'))

@app.route('/profile/skill-edit/delete/<id>')
@login_required
def skill_remove(id):
    db.session.query(UserSkill).filter(UserSkill.user_id==current_user.userid, UserSkill.skill_id==id).delete(synchronize_session="fetch")
    db.session.commit()
    flash("Successfully removed")
    return redirect(url_for('skill_edit'))

class ProfileForm(FlaskForm):
    resume = TextAreaField('description', validators=[InputRequired()])

class SkillForm(FlaskForm):
    skillid = SelectMultipleField('skillid', choices=[], coerce=int)

    def __init__(self, validate_choice=True, *args, **kwargs):
        super(SkillForm, self).__init__(validate_choice=validate_choice, *args, **kwargs)
        SKILL_CHOICES = []
        skills = db.session.query(Skill).all()
        for x in skills:
            SKILL_CHOICES.append((x.id, x.name))
        self.skillid.choices = SKILL_CHOICES
