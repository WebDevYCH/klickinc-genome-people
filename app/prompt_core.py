from model import *
from bs4 import BeautifulSoup

# prompt development for GPT Embedding
def fill_prompt_for_text(object_model, description, category = None):
    soup = BeautifulSoup(description, 'html.parser')
    clean_description = soup.get_text()
    if isinstance(object_model, User):
        prompt = f"Resume for {object_model.firstname} {object_model.lastname}, current title {object_model.title}, who started at Klick in {object_model.started.year}.\n"
        if object_model.enabled:
            prompt += f"{object_model.firstname} works in the {object_model.department} department.\n"
        else:
            prompt += f"{object_model.firstname} is no longer employed here.\n"
        prompt += f"Klick is a marketing agency.\n\n"
        prompt += clean_description
    elif isinstance(object_model, JobPosting):
        # get category name from category id
        prompt = f"Job posting for {object_model.title}, posted on {object_model.posted_date}, with a {category} commitment.\n"
        prompt += f"Job description: {clean_description}"
    else:
        prompt = clean_description
    return prompt
