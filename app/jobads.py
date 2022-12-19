from sqlite3 import Row
from flask_login import login_required
from datetime import date
import json
import requests
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.declarative import DeclarativeMeta
from core import *
from model import *
from core import app
def row2dict(row):
    d = {}
    for column in row.__table__.columns:
        d[column.name] = str(getattr(row, column.name))

###################################################################
## MODEL

Base.classes.job_posting.__str__ = obj_name
Base.classes.job_posting.__json__ = obj_name_joined
JobPosting = Base.classes.job_posting

Base.classes.job_posting_category.__str__ = obj_name
JobPostingCategory = Base.classes.job_posting_category

JobPostingSkill = Base.classes.job_posting_skill

Title = Base.classes.title

###################################################################
## ADMIN

admin.add_view(AdminModelView(JobPosting, db.session, category='Job Ads'))

###################################################################
## FRONTEND

@app.route('/jobads/postjob', methods=['GET', 'POST'])
@login_required
def postjob():
    title = request.form['title']
    category_id = request.form['category_id']
    job_description = request.form['description']
    poster_id = request.form['poster_id']
    posted_date = date.today()
    expiry_date = request.form['expiry_date']

    createJob = JobPosting(job_posting_category_id=category_id, poster_user_id=poster_id, posted_date=posted_date, expiry_date=expiry_date,title=title, description=job_description)
    db.session.add(createJob)
    db.session.commit()
    
    datas = skillSearchAuth(job_description)

    for data in datas:
        skill_name = data['skill']['name']
        skill_description = data['skill']['description']

        db_skill = db.session.query(Skill).filter_by(name = skill_name).first()
        if(db_skill):
            createSkill = JobPostingSkill(job_posting_id = createJob.id, skill_id = db_skill.id)
            db.session.add(createSkill)
            db.session.commit()
        else:
            print('no db skill')
            create_skill = Skill(name = skill_name, description = skill_description)
            db.session.add(create_skill)
            db.session.commit()
            createSkill = JobPostingSkill(job_posting_id = createJob.id, skill_id = create_skill.id)
            db.session.add(createSkill)
            db.session.commit()

    return redirect(url_for('jobsearch'))

@app.route('/jobads/editjob', methods=['GET', 'POST'])
@login_required
def editjob():
    title = request.form['title']
    category_id = request.form['category_id']
    description = request.form['description']
    posted_date = date.today()
    expiry_date = request.form['expiry_date']
    id = request.form['job_posting_id']
    db.session.execute(
        update(JobPosting).
        filter(JobPosting.id == id).
        values(job_posting_category_id=category_id, posted_date=posted_date, expiry_date=expiry_date,title=title, description=description)
    )
    db.session.commit()
    return redirect(url_for('jobsearch'))

@app.route('/jobads/skillsearchauth', methods=['GET', 'POST'])
@login_required
def skillSearchAuth(description):

    url = "https://auth.emsicloud.com/connect/token"

    payload = "client_id="+app.config['LIGHTCAST_API_CLIENTID']+"&client_secret="+app.config['LIGHTCAST_API_SECRET']+"&grant_type=client_credentials&scope="+app.config['LIGHTCAST_API_SCOPE']
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = requests.request("POST", url, data=payload, headers=headers)
    token = json.loads(response.text)

    # for test
    return (skillSearch(token['access_token'], description))

@app.route('/jobads/skillsearch', methods=['GET', 'POST'])
@login_required
def skillSearch(token, data):
    url = "https://emsiservices.com/skills/versions/latest/extract"

    querystring = {"language":"en"}

    payload = {}
    payload['text'] = data
    payload['confidenceThreshold'] = 0.6

    headers = {
        'Authorization': "Bearer "+ token,
        'Content-Type': "application/json"
        }
    response = requests.request("POST", url, data=json.dumps(payload), headers=headers, params=querystring)
    result = json.loads(response.text)
    return(result['data'])

@app.route('/jobads/jobsearch', methods=['GET', 'POST'])
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
            jobs = db.session.query(JobPosting).filter(today-JobPosting.posted_date<delta, JobPosting.title==title).all()
        elif(category_id != 0 and title == 'Select job title'):
            jobs = db.session.query(JobPosting).filter(today-JobPosting.posted_date<delta, JobPosting.job_posting_category_id==category_id).all() 
        elif(category_id == 0 and title == 'Select job title'):
            jobs = db.session.query(JobPosting).filter(today-JobPosting.posted_date<delta).all()
        else:
            jobs = db.session.query(JobPosting).filter(today-JobPosting.posted_date<delta, JobPosting.job_posting_category_id==category_id, JobPosting.title==title).all()
       
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
                # print(dir(r))
                value = {i:v for i, v in r.__dict__.items() if i in r.__table__.columns.keys()}
                result_posting_skill.append(value['name'])
                # print(result_posting_skill)
            result_job['job_posting_skills'] = result_posting_skill
            result.append(result_job)

        return json.dumps(result)
    else:
        delta = 7
        jobs = db.session.query(JobPosting).filter(today-JobPosting.posted_date<delta).all()
        
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
                # print(dir(r))
                value = {i:v for i, v in r.__dict__.items() if i in r.__table__.columns.keys()}
                result_posting_skill.append(value['name'])
                # print(result_posting_skill)
            result_job['job_posting_skills'] = result_posting_skill
            result.append(result_job)
        
    return render_template('jobads/jobsearch.html', jobs=result, categories=categories, titles=titles, csts=csts, jobfunctions=jobfunctions)

@app.route('/jobads/searchpeople', methods=['GET', 'POST'])
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

@app.route('/jobads/applyjob', methods=['GET', 'POST'])
@login_required
def applyjob():
    jobpostingid = request.form['job_posting_id']
    comments = request.form['comments']
    skills = request.form['skills']
    message = request.form['message']
    # Do some DB operation
    return "Applied!"

@app.route('/jobads/getapplicants', methods=['GET', 'POST'])
@login_required
def getapplicants():
    jobpostingid = request.form['job_posting_id']
    # To be fixed for the applicants schema:
    data = db.session.query(User).limit(5).all()
    applicants = json.dumps([{i:v for i, v in r.__dict__.items() if i in r.__table__.columns.keys()} for r in data], default=str)
    return applicants