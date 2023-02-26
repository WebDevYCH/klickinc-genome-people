from flask import json
import requests
import json

from core import *
from model import *

###################################################################
## MODEL

Base.classes.skill.__str__ = obj_name
Skill = Base.classes.skill
UserSkill = Base.classes.user_skill
JobPostingSkill = Base.classes.job_posting_skill

###################################################################
## ADMIN

def get_lightcast_auth_token():
    url = "https://auth.emsicloud.com/connect/token"
    payload = "client_id=" + app.config['LIGHTCAST_API_CLIENTID'] + "&client_secret=" + app.config['LIGHTCAST_API_SECRET'] + "&grant_type=client_credentials&scope=emsi_open"
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}

    response = requests.request("POST", url, data=payload, headers=headers)

    return response.json()['access_token']

def get_allskills_from_lightcast():
    url = "https://emsiservices.com/skills/versions/latest/skills"

    querystring = {"typeIds":"ST1,ST2","fields":"id,name,description"}

    bearer_token = 'Bearer ' + get_lightcast_auth_token()
    headers = {'Authorization': bearer_token}

    response = requests.request("GET", url, headers=headers, params=querystring)

    return response.json()

def extract_skills_from_text(text):
    url = "https://emsiservices.com/skills/versions/latest/extract"

    # querystring = {"language":"fr"}

    payload = make_extract_json_string(text, 0.6)
    bearer_token = 'Bearer ' + get_lightcast_auth_token()
    headers = {
        'Authorization': bearer_token,
        'Content-Type': "application/json"
        }

    response = requests.request("POST", url, data=payload, headers=headers)
    data = response.json()
    return data

def make_extract_json_string(text, threshold):
    result = {
        "text": text,
        "confidenceThreshold": threshold
    }

    json_string = json.dumps(result)

    return json_string

# remove and add skills to User Profile or Job Posting
def auto_fill_skill_from_text(object_model, sourceid = 1):
    relevant_skills = None
    if isinstance(object_model, JobPosting):
        relevant_skills = extract_skills_from_text(object_model.description)
    elif isinstance(object_model, UserProfile):
        relevant_skills = extract_skills_from_text(object_model.resume)
    else: 
        return f"Invalid object model: {object_model.__class__.__name__}"

    # if there was no error, add skills to user
    if "message" in relevant_skills:
        return relevant_skills['message']
    else:
        # gather full list of skills
        full_skills = {}
        for skill in db.session.query(Skill).all():
            full_skills[skill.name] = skill.id  

        # flush existing skills (NOTE: this might be changed to only add new and not remove existing)
        if isinstance(object_model, JobPosting):
            db.session.query(JobPostingSkill).filter(JobPostingSkill.job_posting_id == object_model.id).delete(synchronize_session="fetch")
        elif isinstance(object_model, UserProfile):
            db.session.query(UserSkill).filter(UserSkill.user_id == object_model.user_id).delete(synchronize_session="fetch")

        # fill skills
        for skill in relevant_skills['data']:
            if skill['skill']['name'] in full_skills:
                if isinstance(object_model, JobPosting):
                    createSkill = JobPostingSkill(job_posting_id = object_model.id, skill_id = skill.id)
                elif isinstance(object_model, UserProfile):
                    createSkill = UserSkill(user_id = object_model.user_id, skill_id = skill.id, sourceid = sourceid)
                else:
                    createSkill = None
                
                if (createSkill):
                    db.session.add(createSkill)
                    db.session.commit()

    return "success"
