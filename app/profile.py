from flask import render_template, flash, request
from flask_login import login_required, current_user

from flask_wtf import FlaskForm
from wtforms import SelectField, TextAreaField
from wtforms.validators import InputRequired

from core import *
from model import *
from skillutils import *

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Route to the job."""
    profile = db.session.query(UserProfile).filter(UserProfile.user_id==current_user.userid).one()
    my_skills = db.session.query(Skill).join(UserSkill).where(UserSkill.user_id == current_user.userid).order_by(Skill.name).all()

    if request.method == "POST":
        if profile:
            profile.resume = request.form["resume"]
            db.session.commit()
            flash("Successfully updated your resume")
        else:
            user_profile = UserProfile(resume=request.form["resume"], user_id=int(current_user.userid))
            db.session.add(user_profile)
            db.session.commit()
            flash("Successfully added your resume")
        relevant_skills = extract_skills_from_text(request.form["resume"])
        if "message" in relevant_skills:
            flash("Something error happened! Please wait.")
        else:
            auto_fill_user_skill_from_resume(relevant_skills['data'])
    return render_template('profile/index.html', profile=profile, user=current_user, skills=my_skills)

@app.route('/profile/edit-skills')
@login_required
def resume_skills():
    skills = db.session.query(Skill).join(UserSkill).filter(UserSkill.user_id==current_user.userid).order_by(Skill.name).all()
    return render_template('profile/skill_edit.html', title="Personal Skills", skills=skills)

@app.route('/profile/total-skills-data')
@login_required
def total_skills_data():
    skills = db.session.query(Skill).order_by(Skill.name).all()
    return [{"id": skill.id, "value": skill.name} for skill in skills]

@app.route('/profile/skill-add', methods=['POST'])
@login_required
def skill_add():
    if request.method == "POST":
        newSkills = request.form["newSkills"].split(",")
        for id in newSkills:
            if not db.session.query(UserSkill).filter(UserSkill.user_id==current_user.userid, UserSkill.skill_id==int(id)).first():
                new_skill = UserSkill(skill_id=int(id), user_id=int(current_user.userid), user_skill_source_id=1)
                db.session.add(new_skill)
        db.session.commit()
        flash("Successfully added your skills!") 
    return redirect(url_for('resume_skills'))

@app.route('/profile/skill-edit/delete/<id>')
@login_required
def skill_remove(id):
    db.session.query(UserSkill).filter(UserSkill.user_id==current_user.userid, UserSkill.skill_id==id).delete(synchronize_session="fetch")
    db.session.commit()
    flash("Successfully removed")
    return redirect(url_for('resume_skills'))
