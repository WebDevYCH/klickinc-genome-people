from flask_login import login_required
from datetime import date
from core import *
from model import *
from skills_core import *

###################################################################
## MODEL

Base.classes.job_posting.__str__ = obj_name
Base.classes.job_posting.__json__ = obj_name_joined
JobPosting = Base.classes.job_posting

Base.classes.job_posting_category.__str__ = obj_name
JobPostingCategory = Base.classes.job_posting_category

JobPostingSkill = Base.classes.job_posting_skill

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
