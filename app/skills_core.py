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
def auto_fill_skill_from_text(type, id, description, sourceid = 1):
    relevant_skills = extract_skills_from_text(description)
    # if there was no error, add skills to user
    if "message" in relevant_skills:
        return relevant_skills['message']
    else:
        # gather full list of skills
        full_skills = {}
        for skill in db.session.query(Skill).all():
            full_skills[skill.name] = skill.id  

        # flush existing skills
        if type == 'job_posting':
            db.session.query(JobPostingSkill).filter(JobPostingSkill.job_posting_id == id).delete(synchronize_session="fetch")
        else:
            db.session.query(UserSkill).filter(UserSkill.user_id == id).delete(synchronize_session="fetch")

        # fill skills
        for skill in relevant_skills['data']:
            if skill['skill']['name'] in full_skills:
                if type == 'job_posting':
                    createSkill = JobPostingSkill(job_posting_id = id, skill_id = skill.id)
                else:
                    createSkill = UserSkill(user_id = id, skill_id = skill.id, sourceid = sourceid)
                
                if (createSkill):
                    db.session.add(createSkill)
                    db.session.commit()

    return "success"
