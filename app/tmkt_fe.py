from flask_login import login_required
from datetime import date
import json
from core import *
from model import *
from core import app
from skills_core import *
from flask_login import current_user
from flask import render_template, request, flash

from tmkt_core import *

###################################################################
## FRONTEND

@app.route('/tmkt/postjob', methods=['GET', 'POST'])
@login_required
def postjob():
    # create job_posting object
    job_posting = create_job_posting_object(request.form)

    # save job posting
    flash(save_job_posting(job_posting))

    return job_posting

@app.route('/tmkt/editjob', methods=['GET', 'POST'])
@login_required
def editjob():
    # create job_posting object
    job_posting = create_job_posting_object(request.form)

    # save job posting
    flash(save_job_posting(job_posting))

    return job_posting

@app.route("/tmkt/jobsearch")
@app.route("/tmkt/jobsearch/<view>")
@login_required
def jobsearch(view = None):
    categories = db.session.query(JobPostingCategory).order_by(JobPostingCategory.name).all()
    titles = db.session.query(Title).order_by(Title.name).all()
    csts = db.session.query(User.cst).filter(User.enabled == True).distinct().order_by(User.cst).all()
    csts = [row.cst for row in csts]
    jobfunctions = db.session.query(User.jobfunction).filter(User.enabled == True).distinct().order_by(User.jobfunction).all()
    jobfunctions = [row.jobfunction for row in jobfunctions]

    result = search_job_postings(categories, view = view)
    
    title = "Job Search"
    if view == 'posted':
        title = "Posted Jobs"
    elif view == 'applied':
        title = "Applied Jobs"

    return render_template('tmkt/jobsearch.html', jobs=result, categories=categories, titles=titles, csts=csts, jobfunctions=jobfunctions, title=title)

@app.route('/tmkt/searchpeople', methods=['GET', 'POST'])
@login_required
def searchpeople():
    cst =  request.form['cst']
    jobfunction =  request.form['jobfunction']
    if(cst != 'Select CST' and jobfunction == 'Select job function'):
        data = db.session.query(User).filter(User.enabled == True, User.cst == cst).order_by(User.firstname).all()
    elif(cst == 'Select CST' and jobfunction != 'Select job function'):
        data = db.session.query(User).filter(User.enabled == True, User.jobfunction == jobfunction).order_by(User.firstname).all()
    elif(cst != 'Select CST' and jobfunction != 'Select job function'):
        data = db.session.query(User).filter(User.enabled == True, User.jobfunction == jobfunction, User.cst == cst).order_by(User.firstname).all()
    else:
        data = db.session.query(User).filter(User.enabled == True).order_by(User.firstname).limit(501).all()
    people = json.dumps([{i:v for i, v in r.__dict__.items() if i in r.__table__.columns.keys()} for r in data], default=str)
    return people

@app.route('/tmkt/applyjob', methods=['POST'])
@login_required
def applyjob():
    job_posting_id = request.form['id']
    job_application = get_job_posting_application(job_posting_id, current_user.userid, True).one_or_none()

    if not job_application:
        job_application = JobPostingApplication(job_posting_id = job_posting_id, user_id = current_user.userid)
    
    job_application.applied_date = date.today()
    job_application.cancelled_date = None
    job_application.comments = request.form['comments']
    job_application.skills = request.form['skills']
    job_application.available = 1

    # new fields to be added once FE has been developed
    # apply_job.worked_with_brand = request.form['worked_with_brand']

    try:
        if not job_application.id:
            db.session.add(job_application)
        db.session.commit()
        flash("Successfully applied to job posting")
    except Exception as e:
        flash(f"Error applying to job posting: {e}")

    return job_application

@app.route('/tmkt/getapplicants', methods=['GET', 'POST'])
@login_required
def getapplicants():
    jobpostingid = request.form['job_posting_id']
    # To be fixed for the applicants schema:
    # data = db.session.query(User).limit(5).all()
    data = db.session.query(JobPostingApplication, User).join(User, JobPostingApplication.user_id == User.userid).filter(JobPostingApplication.job_posting_id == jobpostingid, JobPostingApplication.cancelled_date == None).all()
    applicants = json.dumps([{i:v for i, v in r.__dict__.items() if i in r.__table__.columns.keys()} for key, r in data], default=str)
    apply_data = []
    for r, key in data:
        dictA = {i:v for i, v in r.__dict__.items() if i in r.__table__.columns.keys()}
        dictB = {i:v for i, v in key.__dict__.items() if i in key.__table__.columns.keys()}
        dictB['applied_date'] = datetime.datetime.strftime(dictA['applied_date'], "%Y-%m-%d")
        if datetime.datetime.strptime(str(date.today()), "%Y-%m-%d") == datetime.datetime.strptime(str(dictA['applied_date']), "%Y-%m-%d"):
            dictB['applied_date'] = 'Today'
        elif abs(datetime.datetime.strptime(str(date.today()), "%Y-%m-%d") - datetime.datetime.strptime(str(dictA['applied_date']), "%Y-%m-%d")).days == 1:
            dictB['applied_date'] = 'Yesterday'
        apply_data.append(dictB)
    return apply_data

@app.route('/tmkt/setusersetting', methods=['GET', 'POST'])
@login_required
def setusersetting():
    userId = request.form['userId']
    # postId = request.form['postId']
    user_Available = request.form['userAvailable']
    available_user = UserAvailable(user_id = userId, user_av = user_Available)
    db.session.add(available_user)
    db.session.commit()
    return user_Available

@app.route('/tmkt/closepost', methods=['POST'])
@login_required
def closepost():
    # find existing job posting
    job_posting_id = request.form['id']
    job_posting = db.session.query(JobPosting).filter(JobPosting.id==job_posting_id).one()
    if job_posting:
        try:
            job_posting.removed_date = date.today()
            db.session.commit()
            flash("Successfully closed job posting")
        except Exception as e:
            flash(f"Error closing job posting: {e}")
    else:
        flash('Error closing job posting, no job posting found')

    return job_posting

@app.route('/tmkt/cancelapplication', methods=['POST'])
@login_required
def cancelapplication():
    # find existing job application
    job_posting_id = request.form['id']
    user_id = current_user.userid
    job_application = get_job_posting_application(job_posting_id, user_id, False).one_or_none()
    if job_application:
        try:
            job_application.cancelled_date = date.today()
            db.session.commit()
            flash("Successfully cancelled job application")
        except Exception as e:
            flash(f"Error cancelling job application: {e}")
    else:
        flash('Error cancelling application, no application found')

    return job_application
