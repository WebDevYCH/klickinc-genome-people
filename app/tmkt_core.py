from flask_login import login_required
from datetime import date
from core import *
from model import *
from skills_core import *
from flask import render_template, request
from prompt_core import *
import jsonpickle

# create job_posting object from request.form
def create_job_posting_object(request_form):
    # find existing job posting if id is passed in request_form
    try:
        job_posting_id = int(request_form['id'])
    except:
        job_posting_id = 0

    if job_posting_id > 0:
        job_posting = db.session.query(JobPosting).filter(JobPosting.id==job_posting_id).one()
    else:
        job_posting = JobPosting()

    # if unable to find existing record, attempt to reinsert it using the id from the form
    if not job_posting.id:        
        if job_posting_id > 0:
            job_posting.id = job_posting_id
        job_posting.poster_user_id = current_user.userid
        job_posting.posted_date = date.today()

    job_posting.job_posting_category_id = 1
    job_posting.expiry_date = request_form['expiry_date']
    job_posting.title = request_form['title']
    job_posting.description = request_form['description']
    job_posting.expected_hours = request_form['expected_hours']
    job_posting.job_start_date = request_form['job_start_date']
    job_posting.job_end_date = request_form['job_end_date']
    job_posting.cst = request_form['cst']
    job_posting.job_function = request_form['job_function']
    job_posting.client = request_form['client']
    job_posting.brands = request_form['brands']
    job_posting.project_id = request_form['project_id']
    job_posting.hiring_manager = request_form['hiring_manager']
    job_posting.job_location = request_form['job_location']

    # Get GPT3 Embedding value for job posting
    prompt = fill_prompt_for_text(job_posting, job_posting.description)
    job_posting.job_posting_vector = gpt3_embedding(prompt)
    if not isinstance(job_posting.job_posting_vector, list):
        job_posting.job_posting_vector = None

    return job_posting

# save job posting function
def save_job_posting(job_posting, update_skills = True):
    result_msg = None

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
        result = auto_fill_skill_from_text(job_posting)
        if not result == "success":
            result_msg = f"Skill extraction failed: {result}"

    return result_msg

# make job_posting object ready to return to FE
def clean_job_posting_object(job_posting):
    today = date.today()
    d1 = datetime.datetime.strptime(str(today), "%Y-%m-%d")
    d2 = datetime.datetime.strptime(str(job_posting.expiry_date), "%Y-%m-%d")
    job_posting.expiry_sort = (d1 - d2).days
    job_posting.expiry_day = abs(job_posting.expiry_sort)
    job_posting.posted_for = abs((today-job_posting.posted_date).days) 
    job_posting.posted_date = job_posting.posted_date.strftime("%Y-%m-%d")
    job_posting.job_start_date = job_posting.job_start_date.strftime("%Y-%m-%d")
    job_posting.job_end_date = job_posting.job_end_date.strftime("%Y-%m-%d")
    job_posting.expiry_date = job_posting.expiry_date.strftime("%Y-%m-%d")

    return jsonpickle.encode(job_posting)

# generic function to do job search
def search_job_postings(categories = None, view = None):
    # if categories is None, get all categories, ordered by name
    if categories is None:
        categories = db.session.query(JobPostingCategory).order_by(JobPostingCategory.name).all()

    # attempt to find existing user profile
    try:
        profile = db.session.query(UserProfile).filter(UserProfile.user_id==current_user.userid).one()
    except:
        profile = None
        # should we redirect the user to the profile page if they don't have a profile?

    today = date.today()
    filters = []
    
    # if view is not specified, only show active job postings
    # allow user to see removed and expired job postings if they are the poster/applicant
    job_applications = JobPostingApplication()
    if view == 'applied':
        # add filter on active job posting applications for the current user
        filters.append(JobPostingApplication.user_id==current_user.userid)
        filters.append(JobPostingApplication.cancelled_date == None)
        jobs = db.session.query(JobPosting).join(JobPostingApplication, JobPostingApplication.job_posting_id == JobPosting.id).filter(*filters).all()
    else:
        if view == 'posted':
            filters.append(JobPosting.poster_user_id==current_user.userid)
        else:
            job_applications = get_job_posting_application(None, current_user.userid)
            filters.append(JobPosting.removed_date == None)
            filters.append(JobPosting.expiry_date>=today)
        jobs = db.session.query(JobPosting).filter(*filters).all()

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
        
        d1 = datetime.datetime.strptime(str(today), "%Y-%m-%d")
        d2 = datetime.datetime.strptime(str(job.expiry_date), "%Y-%m-%d")
        # adding sort for negative number of days to expiry (so sort reverse order works correctly)
        result_job['expiry_sort'] = (d1 - d2).days
        result_job['expiry_day'] = abs(result_job['expiry_sort'])
        result_job['posted_for'] = abs((today-job.posted_date).days) 
        result_job['posted_date'] = job.posted_date.strftime("%Y-%m-%d")
        result_job['expiry_date'] = job.expiry_date.strftime("%Y-%m-%d")
        if job.job_start_date:
            result_job['job_start_date'] = job.job_start_date.strftime("%Y-%m-%d")
        if job.job_end_date:
            result_job['job_end_date'] = job.job_end_date.strftime("%Y-%m-%d")
        # add cosine similarity between job posting and user profile
        if profile and profile.resume_vector and job.job_posting_vector:
            result_job['similarity'] = cosine_similarity(json.loads(job.job_posting_vector.replace("{", "[").replace("}", "]")), json.loads(profile.resume_vector.replace("{", "[").replace("}", "]")))
        else:
            result_job['similarity'] = 0
        
        # determine if the current user has applied to the jobs in the list
        if view == 'applied':
            # all results are jobs the current user has applied to
            result_job['apply'] = 1
        elif view == 'posted':
            # all results are jobs the current user posted, so they can't apply to them
            result_job['apply'] = 0
        else:
            # get job application status
            job_application = job_applications.filter(JobPostingApplication.job_posting_id == job.id).one_or_none()
            if job_application:
                result_job['apply'] = job_application.available
            else:
                result_job['apply'] = 0
        result.append(result_job)
   
    # sort by similarity
    result.sort(key=lambda x: (x.get('similarity', 0), x.get('expiry_sort', 0)), reverse=True)

    return result

# get job posting application function
def get_job_posting_application(job_posting_id=None, user_id=None, include_cancelled = False):
    filters = []
    if job_posting_id:
        filters.append(JobPostingApplication.job_posting_id==job_posting_id)
    if user_id:
        filters.append(JobPostingApplication.user_id==user_id)
    
    if not include_cancelled:
        filters.append(JobPostingApplication.cancelled_date == None)
    
    return db.session.query(JobPostingApplication).filter(*filters)

# clean job_application object
def clean_job_application(job_application):
    job_application.applied_date = job_application.applied_date.strftime("%Y-%m-%d")
    job_application.cancelled_date = job_application.cancelled_date.strftime("%Y-%m-%d")

    return jsonpickle.encode(job_application)