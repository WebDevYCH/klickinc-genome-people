from flask_login import login_required
from datetime import date
from core import *
from model import *
from skills_core import *
from flask import render_template, request

###################################################################
## MODEL

Base.classes.job_posting.__str__ = obj_name
Base.classes.job_posting.__json__ = obj_name_joined
JobPosting = Base.classes.job_posting

Base.classes.job_posting_category.__str__ = obj_name
JobPostingCategory = Base.classes.job_posting_category

UserAvailable = Base.classes.user_available

JobPostingApplication = Base.classes.job_posting_application

Base.classes.skill.__str__ = obj_name
Skill = Base.classes.skill

Title = Base.classes.title

# save job posting function
def save_job_posting(user, job_posting, update_skills = True):
    result_msg = None
    process_type = "job_posting"

    # Get GPT3 Embedding value for resume
    category = db.session.query(JobPostingCategory).filter(JobPostingCategory.id==job_posting.job_posting_category_id).one().name or None
    prompt = fill_prompt_for_text(process_type, user, job_posting.description, job_posting.title, job_posting.posted_date, category)
    job_posting.job_posting_vector = gpt3_embedding(prompt)
    if not isinstance(job_posting.job_posting_vector, list):
        job_posting.job_posting_vector = None

    try:
        # if job_posting.id doesn't exist, create new job posting; otherwise, update job posting
        if not job_posting.id:
            db.session.add(job_posting)
        db.session.commit()
        result_msg = "Successfully uploaded job posting"
    except Exception as e:
        result_msg = f"Error uploading job posting: {e}"
        update_skills = False

    # extract relevant skills from job posting description
    if update_skills:
        result = auto_fill_skill_from_text(process_type, user.userid, job_posting.description)
        if not result == "success":
            result_msg = f"Skill extraction failed: {result}"

    return result_msg

# apply job posting function
def apply_job_posting(job_application):
    result_msg = None
    try:
        if not job_application.id:
            db.session.add(job_application)
        db.session.commit()
        result_msg = "Successfully applied to job posting"
    except Exception as e:
        result_msg = f"Error applying to job posting: {e}"

    return result_msg

# close job posting function
def close_job_posting(job_posting):
    result_msg = None
    try:
        job_posting.removed_date = date.today()
        db.session.commit()
        result_msg = "Successfully closed job posting"
    except Exception as e:
        result_msg = f"Error closing job posting: {e}"

    return result_msg

# cancel job application function
def cancel_job_application(job_application):
    result_msg = None
    try:
        job_application.cancelled_date = date.today()
        db.session.commit()
        result_msg = "Successfully cancelled job application"
    except Exception as e:
        result_msg = f"Error cancelling job application: {e}"

    return result_msg

# get job posting application function
def get_job_posting_application(job_posting_id, user_id, include_cancelled = False):
    if include_cancelled:
        return db.session.query(JobPostingApplication).filter(JobPostingApplication.job_posting_id==job_posting_id, JobPostingApplication.user_id==user_id, JobPostingApplication.cancelled_date != None).one_or_none()
    else:
        return db.session.query(JobPostingApplication).filter(JobPostingApplication.job_posting_id==job_posting_id, JobPostingApplication.user_id==user_id, JobPostingApplication.cancelled_date == None).one_or_none()

# generic function to do job search
def search_job_postings(categories):
    # attempt to find existing user profile
    try:
        profile = db.session.query(UserProfile).filter(UserProfile.user_id==current_user.userid).one()
    except:
        profile = None
        # should we redirect the user to the profile page if they don't have a profile?

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
        delta = 30
        jobs = db.session.query(JobPosting).filter(today-JobPosting.posted_date<delta, JobPosting.removed_date == None).all()

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
        result_job['posted_date'] = job.posted_date.strftime("%Y-%m-%d")
        result_job['expiry_date'] = job.expiry_date.strftime("%Y-%m-%d")
        # add cosine similarity between job posting and user profile
        if profile and profile.resume_vector and job.job_posting_vector:
            result_job['similarity'] = cosine_similarity(json.loads(job.job_posting_vector.replace("{", "[").replace("}", "]")), json.loads(profile.resume_vector.replace("{", "[").replace("}", "]")))
        else:
            result_job['similarity'] = 0
        result.append(result_job)
    
    # sort by similarity
    result.sort(key=lambda x: (x.get('similarity', 0), x.get('expiry_sort', 0)), reverse=True)

    return result

# render job search page with all the required parameters
def render_job_search_page():
    categories = db.session.query(JobPostingCategory).order_by(JobPostingCategory.name).all()
    # skill = db.session.query(Skill).all()
    titles = db.session.query(Title).order_by(Title.name).all()
    csts = db.session.query(User.cst).filter(User.enabled == True).distinct().order_by(User.cst).all()
    csts = [row.cst for row in csts]
    jobfunctions = db.session.query(User.jobfunction).filter(User.enabled == True).distinct().order_by(User.jobfunction).all()
    jobfunctions = [row.jobfunction for row in jobfunctions]

    result = search_job_postings(categories)

    return render_template('tmkt/jobsearch.html', jobs=result, categories=categories, titles=titles, csts=csts, jobfunctions=jobfunctions, title="Job Search")
