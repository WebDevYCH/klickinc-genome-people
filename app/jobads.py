from flask_login import login_required
from datetime import date
from core import *
from model import *
admin.add_view(AdminModelView(JobPosting, db.session, category='Job Ads'))
@app.route('/jobpost', methods=['GET', 'POST'])
@login_required
def jobpost():
    categories = db.session.query(JobPostingCategory).all()
    return render_template('jobads/jobpost.html', title='Job Post', categories=categories)

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

@app.route('/jobsearch', methods=['GET', 'POST'])
@login_required
def jobsearch():
    jobs = db.session.query(JobPosting).all()
    return render_template('jobads/jobsearch.html', jobs=jobs)