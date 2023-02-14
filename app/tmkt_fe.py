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
    job_posting.job_posting_category_id = request.form['category_id']
    job_posting.poster_user_id = current_user.userid
    job_posting.posted_date = date.today()
    job_posting.expiry_date = request.form['expiry_date']
    job_posting.title = request.form['title']
    job_posting.description = request.form['description']

    # save job posting
    flash(save_job_posting(current_user, job_posting))

    return redirect(url_for('jobsearch'))

@app.route('/tmkt/editjob', methods=['GET', 'POST'])
@login_required
def editjob():
    # find existing job posting
    job_posting_id = request.form['job_posting_id']
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
    job_posting.job_posting_category_id = request.form['category_id']
    job_posting.expiry_date = request.form['expiry_date']
    job_posting.title = request.form['title']
    job_posting.description = request.form['description']

    # save job posting
    flash(save_job_posting(current_user, job_posting))

    return redirect(url_for('jobsearch'))

@app.route("/tmkt/jobsearch-main")
@login_required
def jobmain():
    categories = db.session.query(JobPostingCategory).order_by(JobPostingCategory.name).all()
    # skill = db.session.query(Skill).all()
    titles = db.session.query(Title).order_by(Title.name).all()
    csts = db.session.query(User.cst).filter(User.enabled == True).distinct().order_by(User.cst).all()
    csts = [row.cst for row in csts]
    jobfunctions = db.session.query(User.jobfunction).filter(User.enabled == True).distinct().order_by(User.jobfunction).all()
    jobfunctions = [row.jobfunction for row in jobfunctions]
    today = date.today()
    if request.method == 'POST':
        delta = int(request.form['delta'])
        category_id = int(request.form['category_id'])
        title = request.form['title']
        if(category_id == 0 and title != 'Select job title'):
            jobs = db.session.query(JobPosting).filter(today-JobPosting.posted_date<delta, JobPosting.removed_date == None, JobPosting.title==title).all()
        elif(category_id != 0 and title == 'Select job title'):
            jobs = db.session.query(JobPosting).filter(today-JobPosting.posted_date<delta, JobPosting.removed_date == None, JobPosting.job_posting_category_id==category_id).all() 
        elif(category_id == 0 and title == 'Select job title'):
            jobs = db.session.query(JobPosting).filter(today-JobPosting.posted_date<delta, JobPosting.removed_date == None).all()
        else:
            jobs = db.session.query(JobPosting).filter(today-JobPosting.posted_date<delta, JobPosting.job_posting_category_id==category_id, JobPosting.title==title).all()
    else:
        delta = 7
        jobs = db.session.query(JobPosting).filter(today-JobPosting.posted_date<delta, JobPosting.removed_date == None).all()

    # attempt to find existing user profile
    try:
        profile = db.session.query(UserProfile).filter(UserProfile.user_id==current_user.userid).one()
    except:
        profile = None

    #process the results of the GET or POST (same logic)
    result = []   
    for job in jobs:
        job_posting_skills = db.session.query(JobPostingSkill, Skill).join(Skill, Skill.id == JobPostingSkill.skill_id).join(JobPosting, JobPostingSkill.job_posting_id == job.id).all()
        result_posting_skill = []
        result_job = {i:v for i, v in job.__dict__.items() if i in job.__table__.columns.keys()}
        for category in categories:
            data_category = {i:v for i, v in category.__dict__.items() if i in category.__table__.columns.keys()}
            if data_category['id'] == result_job['job_posting_category_id']:
                result_job['job_posting_category_name'] = data_category['name']
            else:
                continue
        for key, r in job_posting_skills:
            value = {i:v for i, v in r.__dict__.items() if i in r.__table__.columns.keys()}
            result_posting_skill.append(value['name'])
        result_job['job_posting_skills'] = result_posting_skill
        
        apply = get_job_posting_application(job.id, current_user.userid, False)
        result_job['apply'] = 0
        if apply != None:
            apply_value = {i:v for i, v in apply.__dict__.items() if i in apply.__table__.columns.keys()}
            if apply_value['available'] == 1: 
                result_job['apply'] = 1
        d1 = datetime.datetime.strptime(str(today), "%Y-%m-%d")
        d2 = datetime.datetime.strptime(str(job.expiry_date), "%Y-%m-%d")
        # adding sort for negative number of days to expiry (so sort reverse order works correctly)
        result_job['expiry_sort'] = (d1 - d2).days
        result_job['expiry_day'] = abs(result_job['expiry_sort'])
        result_job['posted_for'] = abs((today-job.posted_date).days) 
        # add cosine similarity between job posting and user profile
        if profile and profile.resume_vector and job.job_posting_vector:
            result_job['similarity'] = cosine_similarity(json.loads(job.job_posting_vector.replace("{", "[").replace("}", "]")), json.loads(profile.resume_vector.replace("{", "[").replace("}", "]")))
        else:
            result_job['similarity'] = 0
        result.append(result_job)
    
    # sort by similarity
    result.sort(key=lambda x: (x.get('similarity', 0), x.get('expiry_sort', 0)), reverse=True)

    return render_template('tmkt/jobsearch-main.html', jobs=result, categories=categories, titles=titles, csts=csts, jobfunctions=jobfunctions)

@app.route('/tmkt/jobsearch', methods=['GET', 'POST'])
@login_required
def jobsearch():
    categories = db.session.query(JobPostingCategory).order_by(JobPostingCategory.name).all()

    # skill = db.session.query(Skill).all()
    titles = db.session.query(Title).order_by(Title.name).all()
    csts = db.session.query(User.cst).filter(User.enabled == True).distinct().order_by(User.cst).all()
    csts = [row.cst for row in csts]
    jobfunctions = db.session.query(User.jobfunction).filter(User.enabled == True).distinct().order_by(User.jobfunction).all()
    jobfunctions = [row.jobfunction for row in jobfunctions]
    today = date.today()
    if request.method == 'POST':
        delta = int(request.form['delta'])
        category_id = int(request.form['category_id'])
        title = request.form['title']
        if(category_id == 0 and title != 'Select job title'):
            jobs = db.session.query(JobPosting).filter(today-JobPosting.posted_date<delta, JobPosting.removed_date == None, JobPosting.title==title).all()
        elif(category_id != 0 and title == 'Select job title'):
            jobs = db.session.query(JobPosting).filter(today-JobPosting.posted_date<delta, JobPosting.removed_date == None, JobPosting.job_posting_category_id==category_id).all() 
        elif(category_id == 0 and title == 'Select job title'):
            jobs = db.session.query(JobPosting).filter(today-JobPosting.posted_date<delta, JobPosting.removed_date == None).all()
        else:
            jobs = db.session.query(JobPosting).filter(today-JobPosting.posted_date<delta, JobPosting.job_posting_category_id==category_id, JobPosting.title==title).all()
    else:
        delta = 7
        jobs = db.session.query(JobPosting).filter(today-JobPosting.posted_date<delta, JobPosting.removed_date == None).all()

    # attempt to find existing user profile
    try:
        profile = db.session.query(UserProfile).filter(UserProfile.user_id==current_user.userid).one()
    except:
        profile = None

    #process the results of the GET or POST (same logic)
    result = []   
    for job in jobs:
        job_posting_skills = db.session.query(JobPostingSkill, Skill).join(Skill, Skill.id == JobPostingSkill.skill_id).join(JobPosting, JobPostingSkill.job_posting_id == job.id).all()
        result_posting_skill = []
        result_job = {i:v for i, v in job.__dict__.items() if i in job.__table__.columns.keys()}
        for category in categories:
            data_category = {i:v for i, v in category.__dict__.items() if i in category.__table__.columns.keys()}
            if data_category['id'] == result_job['job_posting_category_id']:
                result_job['job_posting_category_name'] = data_category['name']
            else:
                continue
        for key, r in job_posting_skills:
            value = {i:v for i, v in r.__dict__.items() if i in r.__table__.columns.keys()}
            result_posting_skill.append(value['name'])
        result_job['job_posting_skills'] = result_posting_skill
        
        apply = get_job_posting_application(job.id, current_user.userid, False)
        result_job['apply'] = 0
        if apply != None:
            apply_value = {i:v for i, v in apply.__dict__.items() if i in apply.__table__.columns.keys()}
            if apply_value['available'] == 1: 
                result_job['apply'] = 1
        d1 = datetime.datetime.strptime(str(today), "%Y-%m-%d")
        d2 = datetime.datetime.strptime(str(job.expiry_date), "%Y-%m-%d")
        # adding sort for negative number of days to expiry (so sort reverse order works correctly)
        result_job['expiry_sort'] = (d1 - d2).days
        result_job['expiry_day'] = abs(result_job['expiry_sort'])
        result_job['posted_for'] = abs((today-job.posted_date).days) 
        # add cosine similarity between job posting and user profile
        if profile and profile.resume_vector and job.job_posting_vector:
            result_job['similarity'] = cosine_similarity(json.loads(job.job_posting_vector.replace("{", "[").replace("}", "]")), json.loads(profile.resume_vector.replace("{", "[").replace("}", "]")))
        else:
            result_job['similarity'] = 0
        result.append(result_job)
    
    # sort by similarity
    result.sort(key=lambda x: (x.get('similarity', 0), x.get('expiry_sort', 0)), reverse=True)

    if request.method == 'POST':
        return json.dumps(result, skipkeys=True, default=str, ensure_ascii=False)
    else:
        return render_template('tmkt/jobsearch.html', jobs=result, categories=categories, titles=titles, csts=csts, jobfunctions=jobfunctions)

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
    job_posting_id = request.form['job_posting_id']
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
        flash(close_job_posting(job_posting))
    except:
        # if none exists, flash error
        flash('Error closing job posting')

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
        flash(f'Error cancelling application {e}')

    return redirect(url_for('jobsearch'))
