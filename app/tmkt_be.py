import re
from flask_login import login_required
from datetime import date
import json
from skillutils import *
from flask_login import current_user
from flask import render_template, request

from gpt_index import SimpleDirectoryReader
from gpt_index import GPTSimpleVectorIndex
import PyPDF2
from sklearn.model_selection import train_test_split

from core import *
from model import *
from tmkt_core import *

people_resume_index_dir = "../data/resumes"
people_index_file = "../cache/people_index.json"
people_train_file = "../data/people_train.json"
people_test_file = "../data/people_test.json"

###################################################################
## ADMIN

admin.add_view(AdminModelView(JobPosting, db.session, category='Job Ads'))


###################################################################
## CMDLINE/CRON

# search indexing
@app.cli.command('tmkt_people_index')
def tmkt_people_index_cmd():
    tmkt_people_index()

def tmkt_people_index():
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
@app.cli.command('tmkt_people_test')
def tmkt_people_test_cmd():
    tmkt_people_test()

def tmkt_people_test():
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
@app.cli.command('tmkt_people_interactive')
def tmkt_people_interactive_cmd():
    tmkt_people_interactive()

def tmkt_people_interactive():
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


# search indexing
@app.cli.command('tmkt_people_finetune_create')
def tmkt_people_finetune_create_cmd():
    tmkt_people_finetune_create()

def tmkt_people_finetune_create():
    loglines = AdminLog()
    with app.app_context():
        Base.prepare(autoload_with=db.engine, reflect=True)
    loglines.append(f"CREATING FINETUNE DATA FOR PEOPLE INDEX")

    loglines.append(f"  Loading people resumes from {people_resume_index_dir}")

    trainingdata = []
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
                reader = PyPDF2.PdfReader(open(fullpath, 'rb'))
                for page in reader.pages:
                    prompt += page.extract_text()
            except Exception as e:
                loglines.append(f"    ERROR: Could not read {fullpath}: {e}")
                continue
            prompt += f"\nHow would you summarize this person?\n\n"
            prompt += " -->"

            completion = gpt3_completion(prompt)
            #loglines.append(f"    Prompt for {email}: {prompt}\n========================\n    Completion: {completion}\n========================\n")
            
            trainingdata.append({ "prompt": prompt, "completion": completion })

    loglines.append(f"  Loaded {len(trainingdata)} people resumes")
    traindata, testdata = train_test_split(trainingdata, test_size=0.2, random_state=42)

    # save the training data to jsonl files
    with open(people_train_file, 'w') as outfile:
        for entry in traindata:
            json.dump(entry, outfile)
            outfile.write('\n')
    with open(people_test_file, 'w') as outfile:
        for entry in testdata:
            json.dump(entry, outfile)
            outfile.write('\n')

    loglines.append(f"DONE creating finetune file; to run, running command:")
    loglines.append(f"openai api fine_tunes.create -t {people_train_file} -v {people_test_file} -m davinci")

    return loglines

# search index test
@app.cli.command('tmkt_people_finetune_interactive')
def tmkt_people_finetune_interactive_cmd():
    tmkt_people_finetune_interactive()

def tmkt_people_finetune_interactive():
    loglines = AdminLog()

    engine = "davinci:ft-steve-w-personal-2023-01-22-03-36-33"

    print("Type 'exit' to quit") 
    prompt = ""
    while prompt != "exit":
        prompt = input("Enter a question: ")
        if prompt != "exit":
            results = gpt3_completion(f"Please respond in bulleted form:\n\n{prompt}", engine=engine)
            print(f"Results: {results}")
            print(f"")

    return loglines
