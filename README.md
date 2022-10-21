# Genome People



## Overview


## Deployment
The app requires Python 3.6 as it heavily relies on f-strings. 

You will need to have available MySQL, Python, the requirements in requirements.txt, and 


The app is prepared to be deployed via Docker and run with supervisord. The docker-compose contains three services
* PhpMyAdmin
* MySQL
* Web, which has
    * Nginx
    * uwsgi
    * flask app
