from sqlite3 import Row
from flask_login import login_required
from datetime import date
import json
import pandas as pd
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.declarative import DeclarativeMeta
from core import *
from model import *

###################################################################
## MODEL

Base.classes.job_posting.__str__ = obj_name
Base.classes.job_posting.__json__ = obj_name_joined
JobPosting = Base.classes.job_posting

Base.classes.job_posting_category.__str__ = obj_name
JobPostingCategory = Base.classes.job_posting_category

JobPostingSkill = Base.classes.job_posting_skill

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
        data = json.dumps([{i:v for i, v in r.__dict__.items() if i in r.__table__.columns.keys()} for r in jobs], default=str)
        return data
    else:
        delta = 7
        jobs = db.session.query(JobPosting).join(JobPostingCategory).filter(today-JobPosting.posted_date<delta).all()
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



