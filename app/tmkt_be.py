import re
from flask_login import login_required
from datetime import date
import json
from flask_login import current_user
from flask import render_template, request
import pandas as pd
from bs4 import BeautifulSoup
import pytz

from gpt_index import SimpleDirectoryReader
from gpt_index import GPTSimpleVectorIndex
import pypdf
from sklearn.model_selection import train_test_split

from core import *
from model import *
from tmkt_core import *
from chat_core import *
from skills_core import *
from profile_core import *

people_resume_index_dir = "../data/resumes"
people_index_file = "../cache/people_index.json"
people_train_file = "../data/people_train.json"
people_test_file = "../data/people_test.json"
people_jobs_file = "../data/job-postings-lever.csv"

###################################################################
## ADMIN

admin.add_view(AdminModelView(JobPosting, db.session, category='Job Ads'))


###################################################################
## CMDLINE/CRON

# search indexing
@app.cli.command('tmkt_people_gptindex')
def tmkt_people_gptindex():
    loglines = AdminLog()
    loglines.append(f"TRAINING PEOPLE INDEX")

    loglines.append(f"  Loading people resumes from {people_resume_index_dir}")
    documents = SimpleDirectoryReader(people_resume_index_dir).load_data()
    loglines.append(f"  Loaded {len(documents)} people resumes")

    loglines.append(f"  Creating index")
    index = GPTSimpleVectorIndex(documents, chunk_size_limit=512)

    loglines.append(f"  Saving index to {people_index_file}")
    index.save_to_disk(people_index_file)

    loglines.append(f"DONE")

    return loglines


# search index test
@app.cli.command('tmkt_people_gptindex_test')
def tmkt_people_gptindex_test():
    loglines = AdminLog()
    loglines.append(f"  Testing index")

    index = GPTSimpleVectorIndex.load_from_disk(people_index_file)

    questions = [
        "For the resumes in the list, which people have experience with Python?",
        "Which people have experience with AEM?",
        "Which people have changed jobs a lot?",
        "Which people do you think are not a good fit at a marketing agency?",
    ]
    for question in questions:
        loglines.append(f"  Question: {question}")
        results = index.query(f"Please respond in bulleted form:\n\n{question}", response_mode="compact", similarity_top_k=10)
        loglines.append(f"  Results: {results}")
        loglines.append(f"")

    return loglines

# search index interactively
@app.cli.command('tmkt_people_gptindex_test_interactive')
def tmkt_people_gptindex_test_interactive():
    loglines = AdminLog()
    loglines.append(f"  Testing index")

    index = GPTSimpleVectorIndex.load_from_disk(people_index_file)

    print("Type 'exit' to quit") 
    prompt = ""
    while prompt != "exit":
        prompt = input("Enter a question: ")
        if prompt != "exit":
            results = index.query(f"Please respond in bulleted form:\n\n{prompt}", response_mode="compact", similarity_top_k=10)
            print(f"Results: {results}")
            print(f"")

# chatbot training (test using cmd chat_test, so your questions don't taint the people database)
@app.cli.command('tmkt_chatdb_train')
def tmkt_chatdb_train():
    loglines = AdminLog()
    with app.app_context():
        Base.prepare(autoload_with=db.engine, reflect=True)
    loglines.append(f"CREATING FINETUNE DATA FOR PEOPLE INDEX")

    loglines.append(f"  Loading people resumes from {people_resume_index_dir}")

    chat = Chat("people")

    # for each file in the folder
    peoplecount = 0
    for filename in os.listdir(people_resume_index_dir):
        peoplecount += 1
        fullpath = os.path.join(people_resume_index_dir, filename)
        if os.path.isfile(fullpath) and filename.endswith(".pdf"):
            # convert the PDF to text and craft a prompt for training
            prompt = ""
            email = re.sub(".com-.*", ".com", filename)
            loglines.append(f"  Processing {filename}, email {email}, person {peoplecount}")
            user = db.session.query(User).where(User.email==email).first()
            if user:
                loglines.append(f"    Found user {user.firstname} {user.lastname}")
                prompt += f"Resume for {user.firstname} {user.lastname}, current title {user.title}, who started at Klick in {user.started.year}.\n"
                if user.enabled:
                    prompt += f"{user.firstname} works in the {user.department} department.\n"
                else:
                    prompt += f"{user.firstname} is no longer employed here.\n"
                prompt += f"Klick is a marketing agency.\n\n"
            try:
                reader = pypdf.PdfReader(open(fullpath, 'rb'))
                for page in reader.pages:
                    prompt += page.extract_text().replace("\\n", "\n")
            except Exception as e:
                loglines.append(f"    ERROR: Could not read {fullpath}: {e}")
                continue
            prompt += f"\nHow would you summarize this person?\n\n"

            completion = chat.chat(prompt)
            #loglines.append(f"    Prompt for {email}: {prompt}\n========================\n    Completion: {completion}\n========================\n")

    return loglines

# embeddings test data -- load PDF resumes, load example job postings, and index both with embeddings vectors
@app.cli.command('tmkt_resumes_load_index')
def tmkt_resumes_load_index():
    loglines = AdminLog()
    with app.app_context():
        Base.prepare(autoload_with=db.engine, reflect=True)

    loglines.append(f"  Loading people resumes from {people_resume_index_dir}")
    # for each file in the folder
    peoplecount = 0
    for filename in os.listdir(people_resume_index_dir):
        peoplecount += 1
        fullpath = os.path.join(people_resume_index_dir, filename)
        if os.path.isfile(fullpath) and filename.endswith(".pdf"):
            # convert the PDF to text and craft a prompt for training (prompt is now generated in the save_resume() function)
            email = re.sub(".com-.*", ".com", filename)
            loglines.append(f"  Processing {filename}, email {email}, person {peoplecount}")
            user = db.session.query(User).where(User.email==email).first()
            if user:
                loglines.append(f"    Found user {user.firstname} {user.lastname}")
                resume = ""
                try:
                    reader = pypdf.PdfReader(open(fullpath, 'rb'))
                    for page in reader.pages:
                        resume += page.extract_text().replace("\\n", "\n")
                except Exception as e:
                    loglines.append(f"    ERROR: Could not read {fullpath}: {e}")
                    continue

                # strip out null characters, as sometimes PDF's contain them
                resume = resume.replace('\x00', '')

                result_msg = save_resume(user, resume, False)
                # if result message doesn't start with "Successfully", then it's an error
                if not result_msg.startswith("Successfully"):
                    loglines.append(f"    ERROR: {result_msg}")

# embeddings test data -- load example job postings and index with embeddings vectors
@app.cli.command('tmkt_job_postings_load_index')
def tmkt_job_postings_load_index():
    loglines = AdminLog()
    with app.app_context():
        Base.prepare(autoload_with=db.engine, reflect=True)

    loglines.append(f"Loading job postings from {people_jobs_file}")
    # load csv into dataframe
    df = pd.read_csv(people_jobs_file)
    df = df.fillna('')
    # csv has fields "Posting Title", "Status", "Date Created (UTC)", "Posting Commitment", "Posting Hiring Manager", "Posting Hiring Manager Email", "Description", "ListTitle1", "ListContent1", "ListTitle2", "ListContent2", "ListTitle3", "ListContent3", "ListTitle4", "ListContent4", "ListTitle5", "ListContent5", "Additional"
    for index, row in df.iterrows():
        job_posting = JobPosting()
        loglines.append(f"  Processing job title {row['Posting Title']}, index {index}")

        description = f"""
        <p>{row['Description']}</p>
        <h2>{row['ListTitle1']}</h2>
        <p>{row['ListContent1']}</p>
        <h2>{row['ListTitle2']}</h2>
        <p>{row['ListContent2']}</p>
        <h2>{row['ListTitle3']}</h2>
        <p>{row['ListContent3']}</p>
        <h2>{row['ListTitle4']}</h2>
        <p>{row['ListContent4']}</p>
        <h2>{row['ListTitle5']}</h2>
        <p>{row['ListContent5']}</p>
        <h2>Additional Details</h2>
        <p>{row['Additional']}</p>
        """

        lookup_email = row['Posting Hiring Manager Email']
        if not lookup_email:
            lookup_email = row['Posting Owner Email']
        user = db.session.query(User).where(User.email==lookup_email).first()
        if user:
            job_posting.poster_user_id = user.userid
            loglines.append(f"    Found user {user.firstname} {user.lastname}")

            job_posting.job_posting_category_id = 1 # full time
            if row['Posting Commitment'] == "Part Time":
                job_posting.job_posting_category_id = 2
            elif row['Posting Commitment'] == "Contract":
                job_posting.job_posting_category_id = 3

            # convert date created from UTC to EST
            posted_date = datetime.datetime.strptime(row['Date Created (UTC)'], '%Y-%m-%d %H:%M:%S')
            posted_date = pytz.utc.localize(posted_date)
            posted_date = posted_date.astimezone(pytz.timezone("America/New_York"))
            job_posting.posted_date = posted_date
            job_posting.expiry_date = posted_date + datetime.timedelta(days=90)

            job_posting.title = row['Posting Title']
            job_posting.description = description
            
            result_msg = save_job_posting(user, job_posting)
            # if result message doesn't start with "Successfully", then it's an error
            if not result_msg.startswith("Successfully"):
                loglines.append(f"    ERROR: {result_msg}")
        else:
            loglines.append(f"    ERROR: Could not find user {lookup_email}")

    return loglines

# interactive test: query job matches for a person
@app.cli.command('tmkt_test_query_jobs')
def tmkt_test_query_jobs():
    loglines = AdminLog()
    with app.app_context():
        Base.prepare(autoload_with=db.engine, reflect=True)

    print("Type a user email address, and a list of best-matching jobs will be returned.")
    # load job postings
    jobpostings = db.session.query(JobPosting).filter(JobPosting.posted_date >= datetime.datetime.now() - datetime.timedelta(days=365)).all()

    prompt = ""
    while True:
        prompt = input("\nEmail address: ")
        # load user profile
        user = db.session.query(User).where(User.email==prompt).first()
        if not user:
            print("User not found.")
            continue
        userprofile = db.session.query(UserProfile).where(UserProfile.user_id==user.userid).first()
        if not userprofile:
            print("User profile not found.")
            continue
        if not userprofile.resume_vector:
            print("User profile resume vector not found.")
            continue
        # convert from json string to vector
        resume_vector = json.loads(userprofile.resume_vector.replace("{", "[").replace("}", "]"))

        # find best matching jobs
        scored_jobs = {}
        for jobposting in jobpostings:
            if not jobposting.job_posting_vector:
                continue
            jobposting_vector = json.loads(jobposting.job_posting_vector.replace("{", "[").replace("}", "]"))
            score = cosine_similarity(resume_vector, jobposting_vector)
            if score >= 0.8:
                scored_jobs[jobposting.id] = { "score": score, "jobposting": jobposting }

        # sort by score
        sorted_jobs = sorted(scored_jobs.items(), key=lambda x: x[1]['score'], reverse=True)

        # print top 10 results from the last year
        resultcount = 0
        for job in sorted_jobs:
            print(f"  {job[1]['score']}: {job[1]['jobposting'].title}")
            resultcount += 1
            if resultcount >= 20:
                break


    return loglines

# interactive test: query person matches for a job
@app.cli.command('tmkt_test_query_jobs')
def tmkt_test_query_jobs():
    loglines = AdminLog()
    with app.app_context():
        Base.prepare(autoload_with=db.engine, reflect=True)

    print("Type a user email address, and a list of best-matching jobs will be returned.")
    # load job postings
    jobpostings = db.session.query(JobPosting).filter(JobPosting.posted_date >= datetime.datetime.now() - datetime.timedelta(days=365)).all()

    prompt = ""
    while True:
        prompt = input("\nEmail address: ")
        # load user profile
        user = db.session.query(User).where(User.email==prompt).first()
        if not user:
            print("User not found.")
            continue
        userprofile = db.session.query(UserProfile).where(UserProfile.user_id==user.userid).first()
        if not userprofile:
            print("User profile not found.")
            continue
        if not userprofile.resume_vector:
            print("User profile resume vector not found.")
            continue
        # convert from json string to vector
        resume_vector = json.loads(userprofile.resume_vector.replace("{", "[").replace("}", "]"))

        # find best matching jobs
        scored_jobs = {}
        for jobposting in jobpostings:
            if not jobposting.job_posting_vector:
                continue
            jobposting_vector = json.loads(jobposting.job_posting_vector.replace("{", "[").replace("}", "]"))
            score = cosine_similarity(resume_vector, jobposting_vector)
            if score >= 0.8:
                scored_jobs[jobposting.id] = { "score": score, "jobposting": jobposting }

        # sort by score
        sorted_jobs = sorted(scored_jobs.items(), key=lambda x: x[1]['score'], reverse=True)

        # print top 10 results from the last year
        resultcount = 0
        for job in sorted_jobs:
            print(f"  {job[1]['score']}: {job[1]['jobposting'].title}")
            resultcount += 1
            if resultcount >= 20:
                break


    return loglines
