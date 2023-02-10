from core import *
from skills_core import *

# Resuable save resume function
def save_resume(user, profile, update_skills = True):
    result_msg = None
    process_type = "user_profile"

    # Get GPT3 Embedding value for resume
    prompt = fill_prompt_for_text(process_type, user, profile.resume)
    profile.resume_vector = gpt3_embedding(prompt)
    if not isinstance(profile.resume_vector, list):
        profile.resume_vector = None

    # upload resume to user_profile
    try:
        # Update profile, if it exists. Otherwise, create a new one.
        if not profile.id:
            db.session.add(profile)
        db.session.commit()
        result_msg = "Successfully uploaded resume to User Profile"
    except Exception as e:
        result_msg = f"Error uploading resume to User Profile: {e}"
        update_skills = False

    # extract relevant skills from resume
    if update_skills:
        result = auto_fill_skill_from_text(process_type, user.userid, profile.resume, 1)
        if not result == "success":
            result_msg = f"Skill extraction failed: {result}"

    return result_msg
