from flask_login import login_required
from datetime import date
import json
from core import *
from model import *
from core import app
from skills_core import *
from flask_login import current_user
from flask import render_template, request, flash, jsonify

from tmkt_core import *

###################################################################
## FRONTEND

@app.route('/p/tmkt/postjob', methods=['GET', 'POST'])
@app.route('/p/tmkt/editjob', methods=['GET', 'POST'])
@login_required
def postjob():
    # create job_posting object
    job_posting = create_job_posting_object(request.form)

    # save job posting
    flash(save_job_posting(job_posting))
    
    return clean_job_posting_object(job_posting)

@app.route("/p/tmkt/jobsearch")
@app.route("/p/tmkt/jobsearch/<view>")
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

@app.route('/p/tmkt/searchpeople', methods=['GET', 'POST'])
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

@app.route('/p/tmkt/applyjob', methods=['POST'])
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
    job_application.worked_with_brand = request.form['worked_with_brand']

    try:
        if not job_application.id:
            db.session.add(job_application)
        db.session.commit()
    except Exception as e:
        return jsonify({"message": e,}), 500

    return "Success", 200

@app.route('/p/tmkt/getapplicants', methods=['GET', 'POST'])
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

@app.route('/p/tmkt/setusersetting', methods=['GET', 'POST'])
@login_required
def setusersetting():
    userId = request.form['userId']
    # postId = request.form['postId']
    user_Available = request.form['userAvailable']
    available_user = UserAvailable(user_id = userId, user_av = user_Available)
    db.session.add(available_user)
    db.session.commit()
    return user_Available

@app.route('/p/tmkt/closepost', methods=['POST'])
@login_required
def closepost():
    # find existing job posting
    job_posting_id = request.form['id']
    job_posting = db.session.query(JobPosting).filter(JobPosting.id==job_posting_id).one()
    if job_posting:
        try:
            job_posting.removed_date = date.today()
            db.session.commit()
        except Exception as e:
            return jsonify({"message": e,}), 500
    else:
        return jsonify({"message": "Error closing job posting, no job posting found",}), 400

    return clean_job_posting_object(job_posting)

@app.route('/p/tmkt/cancelapplication', methods=['POST'])
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
        except Exception as e:
            return jsonify({"message": e,}), 500
    else:
        return jsonify({"message": "Error cancelling application, no application found",}), 400

    return clean_job_application(job_application)


# TODO: update to return a list of clients
@app.route('/p/tmkt/client-list')
@login_required
def client_list():
    clients = db.session.query(Portfolio).\
        distinct(Portfolio.clientid,Portfolio.clientname).\
        order_by(Portfolio.clientname).\
        all()

    return [{"id":c.clientid, "value":c.clientname } for c in clients]