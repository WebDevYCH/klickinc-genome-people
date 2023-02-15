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
    job_posting = JobPosting()
    job_posting.job_posting_category_id = request.form['job_posting_category_id']
    job_posting.poster_user_id = current_user.userid
    job_posting.posted_date = date.today()
    job_posting.expiry_date = request.form['expiry_date']
    job_posting.title = request.form['title']
    job_posting.description = request.form['description']

    # new fields to be added once the FE has been developed
    # job_posting.expected_hours = request.form['expected_hours']
    # job_posting.job_start_date = request.form['job_start_date']
    # job_posting.job_end_date = request.form['job_end_date']
    # job_posting.client = request.form['client']
    # job_posting.brands = request.form['brands']
    # job_posting.project_id = request.form['project_id']
    # job_posting.hiring_manager = request.form['hiring_manager']
    # job_posting.job_location = request.form['job_location']
    # job_posting.cst = request.form['cst']
    # job_posting.job_function = request.form['job_function']

    # save job posting
    flash(save_job_posting(current_user, job_posting))

    return redirect(url_for('jobsearch'))

@app.route('/tmkt/editjob', methods=['GET', 'POST'])
@login_required
def editjob():
    # find existing job posting
    job_posting_id = request.form['id']
    try:
        job_posting = db.session.query(JobPosting).filter(JobPosting.id==job_posting_id).one()
    except:
        # if none exists, create new job posting
        job_posting = JobPosting()
        
    # if unable to find existing record, attempt to reinsert it using the id from the form
    if not job_posting.id:        
        job_posting.id = job_posting_id
        job_posting.poster_user_id = current_user.userid
        job_posting.posted_date = date.today()

    # fill job posting with form data
    job_posting.job_posting_category_id = request.form['job_posting_category_id']
    job_posting.expiry_date = request.form['expiry_date']
    job_posting.title = request.form['title']
    job_posting.description = request.form['description']

    # new fields to be added once the FE has been developed
    # job_posting.expected_hours = request.form['expected_hours']
    # job_posting.job_start_date = request.form['job_start_date']
    # job_posting.job_end_date = request.form['job_end_date']
    # job_posting.client = request.form['client']
    # job_posting.brands = request.form['brands']
    # job_posting.project_id = request.form['project_id']
    # job_posting.hiring_manager = request.form['hiring_manager']
    # job_posting.job_location = request.form['job_location']
    # job_posting.cst = request.form['cst']
    # job_posting.job_function = request.form['job_function']

    # save job posting
    flash(save_job_posting(current_user, job_posting))

    return redirect(url_for('jobsearch'))

@app.route("/tmkt/jobsearch")
@login_required
def jobsearch():
    return render_job_search_page()

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
    try:
        apply_job = get_job_posting_application(job_posting_id, current_user.userid, True)
    except:
        apply_job = JobPostingApplication()

    if not apply_job.id:
        apply_job.job_posting_id = job_posting_id
        apply_job.user_id = current_user.userid
    
    apply_job.applied_date = date.today()
    apply_job.cancelled_date = None
    apply_job.comments = request.form['comments']
    apply_job.skills = request.form['skills']
    apply_job.available = 1

    # new fields to be added once FE has been developed
    # apply_job.brand_at_klick = request.form['brand_at_klick']
    # apply_job.brand_before_klick = request.form['brand_before_klick']

    flash(apply_job_posting(apply_job))

    return redirect(url_for('jobsearch'))

@app.route('/tmkt/getapplicants', methods=['GET', 'POST'])
@login_required
def getapplicants():
    jobpostingid = request.form['job_posting_id']
    # To be fixed for the applicants schema:
    # data = db.session.query(User).limit(5).all()
    data = db.session.query(JobPostingApplication, User).join(User, JobPostingApplication.user_id == User.userid).filter(JobPostingApplication.job_id == jobpostingid, JobPostingApplication.cancelled_date == None).all()
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
    return json.dumps(apply_data)

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
    try:
        job_posting_id = request.form['postId']
        job_posting = db.session.query(JobPosting).filter(JobPosting.id==job_posting_id).one()
        if job_posting:
            flash(close_job_posting(job_posting))
        else:
            flash('Error closing job posting, no job posting found')
    except Exception as e:
        # if none exists, flash error
        flash(f'Error closing job posting: {e}')

    return redirect(url_for('jobsearch'))

@app.route('/tmkt/cancelapplication', methods=['POST'])
@login_required
def cancelapplication():
    # find existing job application
    try:
        job_posting_id = request.form['postId']
        user_id = request.form['userId']
        job_apply = get_job_posting_application(job_posting_id, user_id, False)
        if job_apply:
            flash(cancel_job_application(job_apply))
        else:
            flash('Error cancelling application, no application found')
    except Exception as e:
        # if none exists, flash error
        flash(f'Error cancelling application: {e}')

    return redirect(url_for('jobsearch'))
