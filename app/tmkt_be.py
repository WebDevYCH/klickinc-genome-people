from flask_login import login_required
from datetime import date
import json
from core import *
from model import *
from core import app
from skillutils import *
from flask_login import current_user
from flask import render_template, request

from tmkt_core import *

from gpt_index import SimpleDirectoryReader
from gpt_index import GPTSimpleVectorIndex

people_resume_index_dir = "../data/resumes"
people_index_file = "../cache/people_index.json"

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
    loglines.append(f"  Index created")

    loglines.append(f"  Saving index to {people_index_file}")
    index.save_to_disk(people_index_file)
    loglines.append(f"  Index saved")

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
