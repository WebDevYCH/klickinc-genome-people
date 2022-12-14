from sqlite3 import Row
from flask_login import login_required
from datetime import date
import json
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.declarative import DeclarativeMeta
from core import *
from model import *

admin.add_view(AdminModelView(JobPosting, db.session, category='Job Ads'))

@app.route('/jobads/postjob', methods=['GET', 'POST'])
@login_required
def postjob():
    title = request.form['title']
    category_id = request.form['category_id']
    description = request.form['description']
    poster_id = request.form['poster_id']
    posted_date = date.today()
    expiry_date = request.form['expiry_date']
    db.session.execute(
        insert(JobPosting).
        values(job_posting_category_id=category_id, poster_user_id=poster_id, posted_date=posted_date, expiry_date=expiry_date,title=title, description=description)
    )
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

@app.route('/jobads/jobsearch', methods=['GET', 'POST'])
@login_required
def jobsearch():
    categories = db.session.query(JobPostingCategory).order_by(JobPostingCategory.name).all()
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
            jobs = db.session.query(JobPosting).join(JobPostingCategory).filter(today-JobPosting.posted_date<delta, JobPosting.title==title).all()
        elif(category_id != 0 and title == 'Select job title'):
            jobs = db.session.query(JobPosting).join(JobPostingCategory).filter(today-JobPosting.posted_date<delta, JobPosting.job_posting_category_id==category_id).all() 
        elif(category_id == 0 and title == 'Select job title'):
            jobs = db.session.query(JobPosting).join(JobPostingCategory).filter(today-JobPosting.posted_date<delta).all()
        else:
            jobs = db.session.query(JobPosting).join(JobPostingCategory).filter(today-JobPosting.posted_date<delta, JobPosting.job_posting_category_id==category_id, JobPosting.title==title).all()
       
        data = []
        for job in jobs:
            # get json file from database
            data_job = {i:v for i, v in job.__dict__.items() if i in job.__table__.columns.keys()}
            for category in categories:
                data_category = {i:v for i, v in category.__dict__.items() if i in category.__table__.columns.keys()}
                if data_category['id'] == data_job['job_posting_category_id']:
                    data_job['job_posting_category_name'] = data_category['name']
                    data.append(data_job)
                else:
                    continue

        return json.dumps(data)
    else:
        delta = 7
        jobs = db.session.query(JobPosting).join(JobPostingCategory).filter(today-JobPosting.posted_date<delta).all()
        print([{i:v for i, v in r.__dict__.items() if i in r.__table__.columns.keys()} for r in jobs])
        
    
    return render_template('jobads/jobsearch.html', jobs=jobs, categories=categories, titles=titles, csts=csts, jobfunctions=jobfunctions)

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