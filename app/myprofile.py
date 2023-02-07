from flask import render_template, flash, request
from flask_login import login_required, current_user

from core import *
from model import *
from skills_core import *

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    # attempt to find existing profile and skills
    try:
        profile = db.session.query(UserProfile).filter(UserProfile.user_id==current_user.userid).one()
    except:
        profile = None
    try:
        my_skills = db.session.query(Skill).join(UserSkill).where(UserSkill.user_id == current_user.userid).order_by(Skill.name).all()
    except:
        my_skills = None

    if request.method == "POST":
        # get resume from form editor
        resume = request.form['resume']
        
        # Get GPT3 Embedding value for resume
        vector = gpt3_embedding(resume)
        if not isinstance(vector, list):
            vector = None
        
        # Update profile, if it exists. Otherwise, create a new one.
        if profile:
            profile.resume = resume
            profile.resume_vector = vector
            db.session.commit()
            flash("Successfully updated your resume")
        else:
            user_profile = UserProfile(resume=resume, user_id=int(current_user.userid), resume_vector=vector)
            db.session.add(user_profile)
            db.session.commit()
            flash("Successfully added your resume")

        # extract relevant skills from resume
        relevant_skills = extract_skills_from_text(resume)

        # if there was no error, add skills to user
        if "message" in relevant_skills:
            flash("An error happened extracting skills! Please try again.")
        else:
            auto_fill_user_skill_from_resume(current_user.userid, relevant_skills['data'], 1)

    # if there is no profile, flash a message
    if not profile:
        flash("Unable to find an existing profile, please create one by uploading a resume")

    return render_template('profile/index.html', profile=profile, user=current_user, skills=my_skills, title="Profile")

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
