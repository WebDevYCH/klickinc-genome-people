import datetime
import requests

from flask import Flask, render_template, flash, redirect, jsonify, json, url_for, request
from flask_login import LoginManager, login_required, current_user
from flask_admin import expose

from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import Session
from sqlalchemy import MetaData, delete, insert, update, or_, and_

from google.cloud import language_v1
from google.cloud import bigquery

from core import *
from model import *

###################################################################
## DATABASE REPLICATION


def retrieveGenomeReport(queryid):
    apikey = app.config['GENOME_API_TOKEN']
    apiendpoint = app.config['GENOME_API_ROOT']+'/QueryTemplate/Report?_='+apikey
    reqjson = {
        'QueryTemplateID': queryid,
        'TokenIDs': 1,
        'TokenValues': 1
    }
    response = requests.post(apiendpoint, json=reqjson)
    return response.json()


class DbReplicationView(AdminBaseView):
    @expose('/')
    def index(self):
        return self.render('admin/dbrepl.html')

    @expose('/userphotos')
    def userphotos(self):
        loglines = []

        bqclient = bigquery.Client()
        loglines.append("Starting Genome DB Replication via Report Queries")
        loglines.append("")

        # users (just for photos)
        loglines.append("EMPLOYEE LIST (for photos)")
        json = retrieveGenomeReport(1873)
        for uin in json['Entries']:
            #loglines.append(uin)
            #return self.render('admin/job_log.html', loglines=loglines)
            uout = User()
            users = db.session.query(User).where(
                User.email == uin['Email'],
                or_(User.photourl != uin['PhotoURL'], User.photourl == None)).all()
            if len(users) > 0:
                uout = users[0]
                uout.photourl = uin['PhotoURL']
                loglines.append(f"UPDATE user {uin['Email']} {uin['Name']}")
                db.session.commit()

        loglines.append("")

        return self.render('admin/job_log.html', loglines=loglines)

        # portfolio forecasts

class BQReplicationView(AdminBaseView):
    @expose('/')
    def index(self):
        return self.render('admin/bqrepl.html')

    @expose('/users')
    def users(self):
        loglines = []
        bqclient = bigquery.Client()
        loglines.append("Starting Genome DB Replication via BigQuery")
        loglines.append("")

        # users
        loglines.append("USER TABLE")
        sql = f"""
    select  
    UserID,
    ADPEmployeeID,
    LoginName,
    FirstName,
    LastName,
    Email,
    Title,
    Started,
    Departed,
    DepartureType,
    DepartureReason,
    IsBoomerang,
    PreviousUserID,
    Enabled,
    Office,
    SupervisorUserID,
    ScopeL,
    ScopeR,
    EmployeeTypeID,
    CountryID,
    IsPerson,
    LaborRoleID,
    LaborRole,
    LaborCategoryID,
    LaborCategory,
    JobFunctionID,
    JobFunction,
    JobLevelID,
    JobLevel,
    BusinessUnitID,
    CostCenterBUID,
    CostCenter,
    CostCenterTopLevelBUID,
    CostCenterDivisionID,
    BuDivisionBUID,
    BuDivisionTopLevelBUID,
    CST,
    BuDivisionDivisionID,
    CompanyBusinessUnitID,
    DepartmentBusinessUnitID,
    Department
    from `{app.config['BQPROJECT']}.{app.config['BQDATASET']}.DUser`
        """
        row = 0
        for uin in bqclient.query(sql).result():
            # upsert emulation
            uout = User()
            users = db.session.query(User).where(User.userid==uin.UserID).all()
            if len(users) > 0:
                uout = users[0]
            uout.userid = uin.UserID
            uout.adpemployeeid = uin.ADPEmployeeID
            uout.loginname = uin.LoginName
            uout.firstname = uin.FirstName
            uout.lastname = uin.LastName
            uout.email = uin.Email
            uout.title = uin.Title
            uout.started = uin.Started
            uout.departed = uin.Departed
            uout.departuretype = uin.DepartureType
            uout.departurereason = uin.DepartureReason
            uout.isboomerang = uin.IsBoomerang
            uout.previoususerid = uin.PreviousUserID
            uout.enabled = uin.Enabled
            uout.office = uin.Office
            uout.supervisoruserid = uin.SupervisorUserID
            uout.scopel = uin.ScopeL
            uout.scoper = uin.ScopeR
            uout.employeetypeid = uin.EmployeeTypeID
            uout.countryid = uin.CountryID
            uout.isperson = uin.IsPerson
            uout.laborroleid = uin.LaborRoleID
            uout.laborrole = uin.LaborRole
            uout.laborcategoryid = uin.LaborCategoryID
            uout.laborcategory = uin.LaborCategory
            uout.jobfunctionid = uin.JobFunctionID
            uout.jobfunction = uin.JobFunction
            uout.joblevelid = uin.JobLevelID
            uout.joblevel = uin.JobLevel
            uout.businessunitid = uin.BusinessUnitID
            uout.costcenterbuid = uin.CostCenterBUID
            uout.costcenter = uin.CostCenter
            uout.costcentertoplevelbuid = uin.CostCenterTopLevelBUID
            uout.costcenterdivisionid = uin.CostCenterDivisionID
            uout.budivisionbuid = uin.BuDivisionBUID
            uout.budivisiontoplevelbuid = uin.BuDivisionTopLevelBUID
            uout.cst = uin.CST
            uout.budivisiondivisionid = uin.BuDivisionDivisionID
            uout.companybusinessunitid = uin.CompanyBusinessUnitID
            uout.departmentbusinessunitid = uin.DepartmentBusinessUnitID
            uout.department = uin.Department

            if len(users) == 0:
                db.session.add(uout)
                loglines.append(f"NEW user {uin.Email} {uin.FirstName} {uin.LastName}")
            else:
                loglines.append(f"UPDATE user {uin.Email} {uin.FirstName} {uin.LastName}")
            if ++row > 25:
                db.session.commit()
                row = 0
        db.session.commit()

        return self.render('admin/job_log.html', loglines=loglines)

    @expose('/portfolios')
    def portfolios(self):
        loglines = []
        loglines.append("")
        loglines.append("portfolios page")

        return self.render('admin/job_log.html', loglines=loglines)

admin.add_view(DbReplicationView(name='Genome DB', category='DB Replication'))
admin.add_view(BQReplicationView(name='Genome BQ', category='DB Replication'))





