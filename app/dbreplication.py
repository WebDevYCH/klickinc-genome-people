import datetime
import requests

from flask import Flask, render_template, flash, redirect, jsonify, json, url_for, request
from flask_login import LoginManager, login_required, current_user
from flask_admin import expose

from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import Session
from sqlalchemy import MetaData, delete, insert, update, or_, and_

from google.cloud import language_v1

from core import *
from model import *

###################################################################
## DATABASE REPLICATION


class DbReplicationView(AdminBaseView):
    @expose('/')
    def gqueries(self):

        loglines = []

        loglines.append("Starting Genome DB Replication via Report Queries")
        loglines.append("")

        return self.render('admin/job_log.html', loglines=loglines)

admin.add_view(DbReplicationView(name='Genome DB', category='DB Replication'))

