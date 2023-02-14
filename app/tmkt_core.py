from flask_login import login_required
from datetime import date
import json
from core import *
from model import *
from core import app
from skillutils import *
from flask_login import current_user
from flask import render_template, request

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
