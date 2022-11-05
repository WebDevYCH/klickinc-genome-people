# Genome People



## Overview


## Setup

Create and activate a virtual environment::

    virtualenv env
    source env/bin/activate

Install requirements::

    pip install -r 'examples/bootstrap4/requirements.txt'

Run the application::

    ./start-webapp-mac.sh

The first time you run this example, a sample sqlite database gets populated automatically. To suppress this behaviour,
comment the following lines in app.py:::

    if not os.path.exists(database_path):
        build_sample_db()

