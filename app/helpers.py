from flask import json
import requests
import json

from core import *
from model import *

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

def auto_fill_user_skill_from_resume(data):
    db.session.query(UserSkill).filter(UserSkill.user_id == current_user.userid).delete(synchronize_session="fetch")
    for skill in data:
        current_skill =db.session.query(Skill).filter(Skill.name==skill['skill']['name']).first()
        if not db.session.query(UserSkill).filter(UserSkill.user_id == current_user.userid, UserSkill.skill_id==current_skill.id).first():
            new_user_skill = UserSkill(user_id=current_user.userid, skill_id=current_skill.id, user_skill_source_id=1)
            db.session.add(new_user_skill)
    db.session.commit()
    return True

def make_extract_json_string(text, threshold):
    result = {
        "text": text,
        "confidenceThreshold": threshold
    }

    json_string = json.dumps(result)

    return json_string
