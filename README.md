# Genome People



## Overview


## Setup

(Optional) Create and activate a virtual environment::

    virtualenv env
    source env/bin/activate

Install requirements::

    pip install -r requirements.txt

Copy app/config-template.py to app/config.py and add your database credentials::

    cp app/config-template.py app/config.py
    [edit app/config.py]

Run the application::

    ./start-webapp.sh

## Standards and Conventions

- Use singular noun forms for table names, e.g. `job_posting`
- Use camel case for model classes that reflect tables, e.g. `JobPosting`
- Try to keep submodules/mini-applications separate from the core modules if possible, to avoid bloating the core modules. In particular, for an app called `app`:
  - use `app_be.py` for backend code
  - use `app_fe.py` for frontend code
  - use `app_core.py` for shared code and model classes related to this application
  - have `be` and `fe` modules load `core` module only (obviously no circular dependencies)
- Similar to the Python modules, keep templates in a single folder under `templates/`, e.g. `templates/app`


## AI Notes

Completion API can:
- generate new text
- summarize text
- expand text
- answer questions from its corpus
- answer questions about its prompt
- read code
- generate code
- convert code to other code
- (transformers in general can convert from A to B, where A and  B can be things protein->protein_folded)

ChatGPT adds to the completion API:
- short term memory (i.e. previous prompt/completion pairs are added to the context of the new prompt)
- i.e. adds state
- can somehow handle >750 words (chunking and summarization)

LangChain (py lib) adds to the completion API:
- determining when an external source is needed
- bringing in that source

Gpt-Index (py lib) adds to LangChain:
- can bring in SQL databases as a source
- can run SQL directly

Embedding API can:
- convert any text to a ~1500 dimension vector describing its content (semantic meaning)


### Raw Other Notes

THE FUTURE OF GENOME
(Rob, Curt and Aaron are onboard)

3 different realms behind genome.klick.com:
- Genome Original -- OG
- Genome Next Generation -- G2
- Genome People -- GP -- own genome.klick.com/p/, genomeuat.klick.com/p/

GP exists
GP lives in the "Yellow Data" security world



DATA CLASSIFICATION

Red -- ADP, Cost Model, etc. -- salaries for some people, M&A info, super confidential legal corporate stuff
Yellow -- GP -- salaries for most people, DE&I data, surveys, HR/PP
Green -- Genome -- the usual Genome stuff, like project financials, some PII



GENOME PEOPLE

Python
Flask
PostgresQL
On GCP
SQLAlchemy for the model, using reflection at load time
Rails-style rendering
Bootstrap 5
DHTMLx for grids and possibly all forms, but at least many of them


start-web.sh -- yes, it's Mac
    starts Flask
    loads app.py
        loads core.py
        loads model.py
        loads submodules
            core.py
            model.py
            any extra model stuff they have locally
