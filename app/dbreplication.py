import datetime
import re
import hashlib

from flask_admin import expose
from sqlalchemy.ext.serializer import dumps

# from google.cloud import language_v1
from google.cloud import bigquery

from core import *
from model import *

###################################################################
## MODEL CLASSES (possibly redundant to the main modules)

PortfolioForecast = Base.classes.portfolio_forecast


###################################################################
## ADMIN PAGES FOR REPLICATION

class DbReplicationView(AdminBaseView):
    @expose('/')
    def index(self):
        pages = {
            'userphotos': 'Replicate User Photos',
            'portfolioforecasts': 'Replicate Portfolio Forecasts',
        }
        return self.render('admin/job_index.html', title="Genome DB Replication", pages=pages)

    @expose('/userphotos')
    def userphotos(self):
        return self.render('admin/job_log.html', loglines=replicate_userphotos())

    @expose('/portfolioforecasts')
    def portfolioforecasts(self):
        return self.render('admin/job_log.html', loglines=replicate_portfolioforecasts())

@app.cli.command('replicate_userphotos')
def replicate_userphotos_cmd():
    replicate_userphotos()

def replicate_userphotos():
    loglines = AdminLog()
    with app.app_context():
        Base.prepare(autoload_with=db.engine, reflect=True)

    loglines.append("Starting Genome DB Replication via Report Queries")
    loglines.append("")

    # users (just for photos)
    # preload all users, and then for each user in the json, search through the db list
    # and if the photo is different or not set yet, then set it
    loglines.append("EMPLOYEE LIST (for photos)")
    json = retrieveGenomeReport(1873)
    usersdb = {}


    for u in db.session.query(User).all(): 
        usersdb[u.userid] = u

    for uin in json['Entries']:
        if uin['PhotoURL'] != None and uin['Employee'] in usersdb:
            u = usersdb[uin['Employee']]
            if u.photourl == None or u.photourl != uin['PhotoURL']:
                u.photourl = uin['PhotoURL']
                loglines.append(f"UPDATE user {uin['Email']} {uin['Name']} to {u.photourl}")

    loglines.append("")
    db.session.commit()

    return loglines

@app.cli.command('replicate_portfolioforecasts')
def replicate_portfolioforecasts_cmd():
    replicate_portfolioforecasts()

def replicate_portfolioforecasts():
    loglines = AdminLog()
    with app.app_context():
        Base.prepare(autoload_with=db.engine, reflect=True)

    loglines.append("Starting Genome DB Replication via Report Queries")
    loglines.append("")

    loglines.append("PORTFOLIO FORECAST LIST")
    json = retrieveGenomeReport(1705)
    for pfin in json['Entries']:
        pfin['YearMonth'] = parseGenomeDate(pfin['YearMonth'])

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

class BQReplicationView(AdminBaseView):
    @expose('/')
    def index(self):
        pages = {
            'users': 'Replicate Users',
            'portfolios': 'Replicate Portfolios',
            'laborroles': 'Replicate Labor Roles',
            'laborrolehc': 'Replicate Labor Role Headcount'
        }
        return self.render('admin/bqrepl.html', title="BigQuery Replication", pages=pages)

    @expose('/users')
    def users(self):
        return self.render('admin/job_log.html', loglines=replicate_users())

    @expose('/portfolios')
    def portfolios(self):
        return self.render('admin/job_log.html', loglines=replicate_portfolios())

    @expose('/laborroles')
    def laborroles(self):
        return self.render('admin/job_log.html', loglines=replicate_laborroles())

    @expose('/laborrolehc')
    def laborrolehc(self):
        return self.render('admin/job_log.html', loglines=replicate_laborrolehc())


@app.cli.command('replicate_users')
def replicate_users_cmd():
    replicate_users()

def replicate_users():
    loglines = AdminLog()
    with app.app_context():
        Base.prepare(autoload_with=db.engine, reflect=True)
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
    rowcount = 0
    for uin in bqclient.query(sql).result():
        upsert(db.session, User, {"userid": uin.UserID}, {
            "userid": uin.UserID,
            "adpemployeeid": uin.ADPEmployeeID,
            "loginname": uin.LoginName,
            "firstname": uin.FirstName,
            "lastname": uin.LastName,
            "email": uin.Email,
            "title": uin.Title,
            "started": uin.Started,
            "departed": uin.Departed,
            "departuretype": uin.DepartureType,
            "departurereason": uin.DepartureReason,
            "isboomerang": uin.IsBoomerang,
            "previoususerid": uin.PreviousUserID,
            "enabled": uin.Enabled,
            "office": uin.Office,
            "supervisoruserid": uin.SupervisorUserID,
            "scopel": uin.ScopeL,
            "scoper": uin.ScopeR,
            "employeetypeid": uin.EmployeeTypeID,
            "countryid": uin.CountryID,
            "isperson": uin.IsPerson,
            "laborroleid": uin.LaborRoleID,
            "laborrole": uin.LaborRole,
            "laborcategoryid": uin.LaborCategoryID,
            "laborcategory": uin.LaborCategory,
            "jobfunctionid": uin.JobFunctionID,
            "jobfunction": uin.JobFunction,
            "joblevelid": uin.JobLevelID,
            "joblevel": uin.JobLevel,
            "businessunitid": uin.BusinessUnitID,
            "costcenterbuid": uin.CostCenterBUID,
            "costcenter": uin.CostCenter,
            "costcentertoplevelbuid": uin.CostCenterTopLevelBUID,
            "costcenterdivisionid": uin.CostCenterDivisionID,
            "budivisionbuid": uin.BuDivisionBUID,
            "budivisiontoplevelbuid": uin.BuDivisionTopLevelBUID,
            "cst": uin.CST,
            "budivisiondivisionid": uin.BuDivisionDivisionID,
            "companybusinessunitid": uin.CompanyBusinessUnitID,
            "departmentbusinessunitid": uin.DepartmentBusinessUnitID,
            "department": uin.Department
        })

        rowcount += 1
        if rowcount % 100 == 0:
            loglines.append(f"Processed {rowcount} rows")
            db.session.commit()

    loglines.append(f"Processed {rowcount} rows")
    db.session.commit()

    return loglines

@app.cli.command('replicate_portfolios')
def replicate_portfolios_cmd():
    replicate_portfolios()

def replicate_portfolios():
    loglines = AdminLog()
    with app.app_context():
        Base.prepare(autoload_with=db.engine, reflect=True)
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
    rowcount = 0
    for pfin in bqclient.query(sql).result():
        upsert(db.session, Portfolio, {'accountportfolioid': pfin.accountportfolioid}, {
            'name': pfin.name,
            'clientname': pfin.clientname,
            'currcst': pfin.currcst,
            'currbusinessunit': pfin.currbusinessunit,
            'currcostcenter': pfin.currcostcenter,
            'currgadname': pfin.currgadname,
            'currpdname': pfin.currpdname,
            'currstratname': pfin.currstratname,
            'currcdname': pfin.currcdname,
            'currtdname': pfin.currtdname,
            'currofficename': pfin.currofficename
        })

        rowcount += 1
        if rowcount % 100 == 0:
            print(f"Processed {rowcount} rows")

    loglines.append(f"Processed {rowcount} rows")
    db.session.commit()

    return loglines

@app.cli.command('replicate_laborroles')
def replicate_laborroles_cmd():
    replicate_laborroles()

def replicate_laborroles():
    loglines = AdminLog()
    with app.app_context():
        Base.prepare(autoload_with=db.engine, reflect=True)
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
    rowcount = 0
    for lrin in bqclient.query(sql).result():
        upsert(db.session, LaborRole, { 'id': lrin.laborroleid }, {
            'id': lrin.laborroleid,
            'name': lrin.name,
            'jobfunction': lrin.jobfunction,
            'joblevel': lrin.joblevel,
            'categoryname': lrin.categoryname
        })
        rowcount += 1
        if rowcount % 100 == 0:
            db.session.commit()
            loglines.append(f"  {rowcount} rows")

    loglines.append(f"Processed {rowcount} rows")
    db.session.commit()
    return loglines

@app.cli.command('replicate_laborrolehc')
def replicate_laborrolehc_cmd():
    replicate_laborrolehc()

def replicate_laborrolehc():
    loglines = AdminLog()
    with app.app_context():
        Base.prepare(autoload_with=db.engine, reflect=True)
    bqclient = bigquery.Client()
    loglines.append("Starting Genome DB Replication via BigQuery")
    loglines.append("")

    # users
    loglines.append("LABORROLE HEADCOUNT TABLE")
    sql = f"""
select LAST_DAY(uwd.YearMonthDay) as YearMonth, CST, LaborRoleID, EmployeeTypeID, 
count(*) as HeadCount
from `{app.config['BQPROJECT']}.{app.config['BQDATASET']}.DUserWorkDay` uwd
where uwd.YearMonthDay =  LAST_DAY(uwd.YearMonthDay)
and EmployeeTypeID in ('PM','CN')
and uwd.YearMonthDay > date('2015-01-01')
group by CST, LaborRoleID, EmployeeTypeID, YearMonth
order by 1 desc
    """
    rowcount = 0
    for lrhcin in bqclient.query(sql).result():
        upsert(db.session, LaborRoleHeadcount, {
            'yearmonth': lrhcin.YearMonth,
            'cstname': lrhcin.CST,
            'laborroleid': lrhcin.LaborRoleID,
            'employeetypeid': lrhcin.EmployeeTypeID
        }, { 'headcount_eom': lrhcin.HeadCount })
        rowcount += 1
        if rowcount % 100 == 0:
            db.session.commit()
            loglines.append(f"  {rowcount} rows")

    loglines.append(f"Processed {rowcount} rows")
    db.session.commit()
    return loglines



admin.add_view(DbReplicationView(name='Genome DB', category='DB Replication'))
admin.add_view(BQReplicationView(name='Genome BQ', category='DB Replication'))
