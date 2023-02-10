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
    title = request.form['title']
    category_id = request.form['category_id']
    job_description = request.form['description']
    poster_id = request.form['poster_id']
    posted_date = date.today()
    expiry_date = request.form['expiry_date']
        
    # Get GPT3 Embedding value for resume
    vector = gpt3_embedding(job_description)
    if not isinstance(vector, list):
        vector = None

    createJob = JobPosting(job_posting_category_id=category_id, poster_user_id=poster_id, posted_date=posted_date, expiry_date=expiry_date,title=title,description=job_description,job_posting_vector=vector)
    db.session.add(createJob)
    db.session.commit()

    # extract relevant skills from job posting description
    result = auto_fill_skill_from_text("user_profile", current_user.userid, job_description)
    if not result == "success":
        flash(f"Skill extraction failed: {result}")

    return redirect(url_for('jobsearch'))

@app.route('/tmkt/editjob', methods=['GET', 'POST'])
@login_required
def editjob():
    title = request.form['title']
    category_id = request.form['category_id']
    description = request.form['description']
    expiry_date = request.form['expiry_date']
    id = request.form['job_posting_id']
        
    # Get GPT3 Embedding value for resume
    vector = gpt3_embedding(description)
    if not isinstance(vector, list):
        vector = None

    upsert(db.session, JobPosting, {'id': id}, {'job_posting_category_id': category_id, 'expiry_date': expiry_date, 'title': title, 'description': description, 'job_posting_vector': vector})
    db.session.commit()

    # extract relevant skills from job posting description
    result = auto_fill_skill_from_text("user_profile", current_user.userid, description)
    if not result == "success":
        flash(f"Skill extraction failed: {result}")

    return redirect(url_for('jobsearch'))

@app.route("/tmkt/jobsearch-main")
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
        
        apply = db.session.query(ApplyJob).filter(ApplyJob.job_id == job.id, ApplyJob.user_id == current_user.userid).first()
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
        
        apply = db.session.query(ApplyJob).filter(ApplyJob.job_id == job.id, ApplyJob.user_id == current_user.userid).first()
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

@app.route('/tmkt/applyjob', methods=['GET', 'POST'])
@login_required
def applyjob():
    jobpostingid = request.form['job_posting_id']
    comments = request.form['comments']
    skills = request.form['skills']
    userId = request.form['userId']
    apply_job = ApplyJob(user_id = userId, job_id = jobpostingid, comments = comments, skills =skills, applied_date = date.today())
    db.session.add(apply_job)
    db.session.commit()

    return "Applied!"

@app.route('/tmkt/getapplicants', methods=['GET', 'POST'])
@login_required
def getapplicants():
    jobpostingid = request.form['job_posting_id']
    # To be fixed for the applicants schema:
    # data = db.session.query(User).limit(5).all()
    data = db.session.query(ApplyJob, User).join(User, ApplyJob.user_id == User.userid).filter(ApplyJob.job_id == jobpostingid).all()
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

@app.route('/tmkt/closepost', methods=['GET', 'POST'])
@login_required
def closepost():
    userId = request.form['userId']
    postId = request.form['postId']
    upsert(JobPosting, {'id': postId}, {'removed_date': date.today()})
    db.session.commit()
    return userId

@app.route('/tmkt/cancelapplication', methods=['GET', 'POST'])
@login_required
def cancelapplication():
    userId = request.form['userId']
    postId = request.form['postId']
    db.session.execute(ApplyJob).filter(ApplyJob.user_id == userId, ApplyJob.job_id == postId).delete()

    db.session.commit()
    return redirect(url_for('jobsearch'))
