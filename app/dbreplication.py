import datetime
import requests

from flask import Flask, render_template, flash, redirect, jsonify, json, url_for, request
from flask_login import LoginManager, login_required, current_user
from flask_admin import expose

from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import Session
from sqlalchemy import MetaData, delete, insert, update, or_, and_, select

from sqlalchemy.ext.serializer import loads, dumps

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
        # preload all users, and then for each user in the json, search through the db list
        # and if the photo is different or not set yet, then set it
        loglines.append("EMPLOYEE LIST (for photos)")
        json = retrieveGenomeReport(1873)
        usersdb = db.session.query(User).all()
        for uin in json['Entries']:
            if uin['PhotoURL'] != None:
                uout = User()
                for u in usersdb:
                    if u.userid == uin['Employee'] and (u.photourl == None or u.photourl != uin['PhotoURL']):
                        u.photourl = uin['PhotoURL']
                        loglines.append(f"UPDATE user {uin['Email']} {uin['Name']} to {u.photourl}")

        loglines.append("")
        db.session.commit()

        return self.render('admin/job_log.html', loglines=loglines)

    @expose('/portfolioforecasts')
    def portfolioforecasts(self):
        loglines = []

        bqclient = bigquery.Client()
        loglines.append("Starting Genome DB Replication via Report Queries")
        loglines.append("")

        loglines.append("PORTFOLIO FORECAST LIST")
        json = retrieveGenomeReport(1705)
        for pfin in json['Entries']:
            # date comes back in the format '/Date(1262322000000-0500)/', ie milliseconds since 1970-01-01
            pfin['YearMonth'] = datetime.datetime.fromtimestamp(int(pfin['YearMonth'][6:16]))

            newupdateskip = 'u'
            pfout = db.session.query(PortfolioForecast).where(
                PortfolioForecast.portfolioid == pfin['AccountPortfolioID'],
                PortfolioForecast.yearmonth == pfin['YearMonth']
                ).first()
            if pfout == None:
                pfout = PortfolioForecast()
                newupdateskip = 'n'

            # do we even know this portfolio? (skip if not)
            if db.session.query(Portfolio).where(Portfolio.id == pfin['AccountPortfolioID']).first() == None:
                newupdateskip = 's'
            # skip if they're the same
            pfinsig = f"{pfin['TEARevenue']} {pfin['FEARevenue']} {pfin['AEARevenue']} {pfin['LEARevenue']}"
            pfoutsig = f"{pfout.portfolioid} {pfout.yearmonth} {pfout.target} {pfout.forecast} {pfout.actuals} {pfout.lbeforecast}"
            if pfinsig == pfoutsig:
                newupdateskip = 's'
            # skip if forecast is older than 2020
            if pfin['YearMonth'] < datetime.datetime(2020,1,1):
                newupdateskip = 's'

            if newupdateskip == 'u' or newupdateskip == 'n':
                pfout.portfolioid = pfin['AccountPortfolioID']
                pfout.yearmonth = pfin['YearMonth']
                pfout.target = pfin['TEARevenue']
                pfout.forecast = pfin['FEARevenue']
                pfout.actuals = pfin['AEARevenue']
                pfout.lbeforecast = pfin['LEARevenue']

            if newupdateskip == 'n':
                db.session.add(pfout)
                loglines.append(f"NEW portfolio forecast {pfout.portfolioid} {pfout.yearmonth}")
            elif newupdateskip == 's':
                loglines.append(f"SKIP portfolio forecast {pfout.portfolioid} {pfout.yearmonth}")
            else:
                loglines.append(f"UPDATE portfolio forecast {pfout.portfolioid} {pfout.yearmonth}")
            db.session.commit()

        loglines.append("")
        db.session.commit()

        return self.render('admin/job_log.html', loglines=loglines)

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
        for uin in bqclient.query(sql).result():
            # upsert emulation
            uout = User()
            users = db.session.query(User).where(User.userid==uin.UserID).all()
            if len(users) > 0:
                uout = users[0]
            uout_serialized = dumps(uout)
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
                if dumps(uout) != uout_serialized:
                    loglines.append(f"UPDATE user {uin.Email} {uin.FirstName} {uin.LastName}")
                else:
                    loglines.append(f"SKIP user {uin.Email} {uin.FirstName} {uin.LastName}")

        db.session.commit()

        return self.render('admin/job_log.html', loglines=loglines)

    @expose('/portfolios')
    def portfolios(self):
        loglines = []
        bqclient = bigquery.Client()
        loglines.append("Starting Genome DB Replication via BigQuery")
        loglines.append("")

        # users
        loglines.append("PORTFOLIO TABLE")
        sql = f"""
SELECT distinct accountportfolioid,
name, clientname, currcst, currbusinessunit, currcostcenter, 
currgadname, currpdname, currstratname, currcdname, currtdname, currofficename
from `{app.config['BQPROJECT']}.{app.config['BQDATASET']}.Portfolio`
        """
        for pfin in bqclient.query(sql).result():
            # upsert emulation
            pfout = Portfolio()
            newupdateskip = 'n'
            portfolios = db.session.query(Portfolio).where(Portfolio.id==pfin.accountportfolioid).all()
            if len(portfolios) > 0:
                pfout = portfolios[0]
                newupdateskip = 's'

            pfinsig = f"{pfin.name} {pfin.clientname} {pfin.currcst} {pfin.currbusinessunit} {pfin.currcostcenter} {pfin.currgadname} {pfin.currpdname} {pfin.currstratname} {pfin.currcdname} {pfin.currtdname} {pfin.currofficename}"
            pfoutsig = f"{pfout.name} {pfout.clientname} {pfout.currcst} {pfout.currbusinessunit} {pfout.currcostcenter} {pfout.currgadname} {pfout.currpdname} {pfout.currstratname} {pfout.currcdname} {pfout.currtdname} {pfout.currofficename}"

            if pfinsig != pfoutsig:
                if newupdateskip == 's':
                    newupdateskip = 'u'
                pfout.id = pfin.accountportfolioid
                pfout.name = pfin.name
                pfout.clientname = pfin.clientname
                if pfin.currcst != None:
                    pfout.currcst = pfin.currcst
                pfout.currbusinessunit = pfin.currbusinessunit
                pfout.currcostcenter = pfin.currcostcenter
                pfout.currgadname = pfin.currgadname
                pfout.currpdname = pfin.currpdname
                pfout.currstratname = pfin.currstratname
                pfout.currcdname = pfin.currcdname
                pfout.currtdname = pfin.currtdname
                pfout.currofficename = pfin.currofficename

            if newupdateskip == 'n':
                db.session.add(pfout)
                loglines.append(f"NEW portfolio {pfout.name}")
            elif newupdateskip == 's':
                loglines.append(f"SKIP portfolio {pfout.name}")
            else:
                loglines.append(f"UPDATE portfolio {pfout.name}")
                loglines.append(f"  [INBOUND : {pfinsig}]")
                loglines.append(f"  [EXISTING: {pfoutsig}]")

        db.session.commit()

        return self.render('admin/job_log.html', loglines=loglines)

    @expose('/laborroles')
    def laborroles(self):
        loglines = []
        bqclient = bigquery.Client()
        loglines.append("Starting Genome DB Replication via BigQuery")
        loglines.append("")

        # users
        loglines.append("LABORROLE TABLE")
        sql = f"""
SELECT 
distinct laborroleid, defaultname as name, jobfunction, joblevel, categoryname 
from `{app.config['BQPROJECT']}.{app.config['BQDATASET']}.DLaborRole`
        """
        for lrin in bqclient.query(sql).result():
            # upsert emulation
            lrout = LaborRole()
            newupdateskip = 'n'
            laborroles = db.session.query(LaborRole).where(LaborRole.id==lrin.laborroleid).all()
            if len(laborroles) > 0:
                lrout = laborroles[0]
                newupdateskip = 's'

            lrinsig = f"{lrin.name} {lrin.jobfunction} {lrin.joblevel} {lrin.categoryname}"
            lroutsig = f"{lrout.name} {lrout.jobfunction} {lrout.joblevel} {lrout.categoryname}"

            if lrinsig != lroutsig:
                if newupdateskip == 's':
                    newupdateskip = 'u'
                lrout.id = lrin.laborroleid
                lrout.name = lrin.name
                lrout.jobfunction = lrin.jobfunction
                lrout.joblevel = lrin.joblevel
                lrout.categoryname = lrin.categoryname

            if newupdateskip == 'n':
                db.session.add(lrout)
                loglines.append(f"NEW labor role {lrout.name}")
            elif newupdateskip == 's':
                loglines.append(f"SKIP labor role {lrout.name}")
            else:
                loglines.append(f"UPDATE labor role {lrout.name}")
                loglines.append(f"  [INBOUND : {lrinsig}]")
                loglines.append(f"  [EXISTING: {lroutsig}]")

        db.session.commit()

        return self.render('admin/job_log.html', loglines=loglines)

admin.add_view(DbReplicationView(name='Genome DB', category='DB Replication'))
admin.add_view(BQReplicationView(name='Genome BQ', category='DB Replication'))




