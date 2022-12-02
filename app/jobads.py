from sqlite3 import Row
from flask_login import login_required
from datetime import date
import simplejson
import json
import pandas as pd
from bson import json_util
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.declarative import DeclarativeMeta
from core import *
from model import *

admin.add_view(AdminModelView(JobPosting, db.session, category='Job Ads'))

@app.route('/postjob', methods=['GET', 'POST'])
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

@app.route('/editjob', methods=['GET', 'POST'])
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

@app.route('/jobsearch', methods=['GET', 'POST'])
@login_required
def jobsearch():
    categories = db.session.query(JobPostingCategory).all()
    titles = db.session.query(Title).all()
    today = date.today()
    if request.method == 'POST':
        delta = int(request.form['delta'])
        category_id = int(request.form['category_id'])
        title = request.form['title']
        if(category_id == 0 and title != 'Select job title'):
            jobs = db.session.query(JobPosting).join(JobPostingCategory).filter(today-JobPosting.posted_date<delta, JobPosting.title==title).all()
            data = json.dumps([{i:v for i, v in r.__dict__.items() if i in r.__table__.columns.keys()} for r in jobs], default=str)
            return data  
        elif(category_id != 0 and title == 'Select job title'):
            jobs = db.session.query(JobPosting).join(JobPostingCategory).filter(today-JobPosting.posted_date<delta, JobPosting.job_posting_category_id==category_id).all()
            data = json.dumps([{i:v for i, v in r.__dict__.items() if i in r.__table__.columns.keys()} for r in jobs], default=str)
            return data       
        elif(category_id == 0 and title == 'Select job title'):
            jobs = db.session.query(JobPosting).join(JobPostingCategory).filter(today-JobPosting.posted_date<delta).all()
            data = json.dumps([{i:v for i, v in r.__dict__.items() if i in r.__table__.columns.keys()} for r in jobs], default=str)
            return data
        else:
            jobs = db.session.query(JobPosting).join(JobPostingCategory).filter(today-JobPosting.posted_date<delta, JobPosting.job_posting_category_id==category_id, JobPosting.title==title).all()
            data = json.dumps([{i:v for i, v in r.__dict__.items() if i in r.__table__.columns.keys()} for r in jobs], default=str)
            return data
    else:
        delta = 7
        jobs = db.session.query(JobPosting).join(JobPostingCategory).filter(today-JobPosting.posted_date<delta).all()

    return render_template('jobads/jobsearch.html', jobs=jobs, categories=categories, titles=titles)
