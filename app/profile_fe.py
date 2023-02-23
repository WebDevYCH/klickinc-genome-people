from flask import render_template, flash, request
from flask_login import login_required, current_user

from core import *
from model import *
from skills_core import *
from profile_core import *

@app.route('/profile', methods=['GET', 'POST'])
@app.route('/profile/<selected_user_id>', methods=['GET'])
@login_required
def profile(selected_user_id = None):

    result = None
    if request.method == "POST":
        # if not profile exists, create a new model
        if not profile:
            profile = UserProfile(user_id=int(current_user.userid))
        # get resume from form editor
        profile.resume = request.form['resume']
        # save resume to user profile
        result = save_resume(current_user, profile)
        # flash results message
        if result:
            flash(result)
    else:
        if selected_user_id:
            # get user profile from user_id passed in url
            try:
                profile = db.session.query(UserProfile).filter(UserProfile.user_id==selected_user_id).one()
            except:
                profile = None
                result = "Unable to find an existing profile for user id: " + selected_user_id
        else:
            # attempt to find current user's profile
            try:
                profile = db.session.query(UserProfile).filter(UserProfile.user_id==current_user.userid).one()
            except:
                profile = None
                result = "Unable to find an existing profile, please create one by uploading a resume"
        # if there is no profile, flash a message
        if not profile:
            flash(result)

    # attempt to find existing skills
    try:
        my_skills = db.session.query(Skill).join(UserSkill).where(UserSkill.user_id == current_user.userid).order_by(Skill.name).all()
    except:
        my_skills = None

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

# GET /users
@app.route('/users/user-list')
@login_required
def users():
    users = db.session.query(User).\
        filter(User.enabled).\
        filter(User.isperson).\
        order_by(User.lastname, User.firstname).\
        all()
    #return list of userids and first/last names
    return [{"id": user.userid, "value": user.firstname + " " + user.lastname} for user in users]
