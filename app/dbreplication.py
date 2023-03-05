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
    rowcount = 0
    for pfin in json['Entries']:
        pfin['YearMonth'] = parseGenomeDate(pfin['YearMonth'])

        if pfin['AccountPortfolioID'] in [496,587,855]:
            #skip this one
            continue

        if upsert(db.session, PortfolioForecast, 
            { 
                'portfolioid': pfin['AccountPortfolioID'],
                'yearmonth': pfin['YearMonth']
            }, 
            {
                'target': pfin['TEARevenue'],
                'forecast': pfin['FEARevenue'],
                'actuals': pfin['AEARevenue'],
                'lbeforecast': pfin['LEARevenue']
            }, usecache=False):
            #loglines.append(f"Inserted/updated portfolio forecast {pfin['AccountPortfolioID']} {pfin['YearMonth']}")
            pass

        rowcount += 1
        if rowcount % 100 == 0:
            loglines.append(f"ROW {rowcount}")
            db.session.commit()

    loglines.append("PROCESSED {rowcount} rows")
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
        if upsert(db.session, User, {"userid": uin.UserID}, {
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
        }, usecache=True):
            loglines.append(f"Inserted/updated user {uin.UserID} {uin.FirstName} {uin.LastName}")

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
        if upsert(db.session, Portfolio, {'id': pfin.accountportfolioid}, {
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
        }, usecache=True):
            loglines.append(f"Inserted/updated portfolio {pfin.accountportfolioid} {pfin.clientname} - {pfin.name}")

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
        if upsert(db.session, LaborRole, { 'id': lrin.laborroleid }, {
            'name': lrin.name,
            'jobfunction': lrin.jobfunction,
            'joblevel': lrin.joblevel,
            'categoryname': lrin.categoryname
        }, usecache=True):
            loglines.append(f"Inserted/updated laborrole {lrin.laborroleid} {lrin.name}")
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

    # delete recent data first
    db.session.query(LaborRoleHeadcount).filter(LaborRoleHeadcount.yearmonth >= datetime.date.today() - datetime.timedelta(days=60)).delete()

    # pull data from bigquery
    loglines.append("LABORROLE HEADCOUNT TABLE")
    sql = f"""
  select LAST_DAY(uwd.YearMonthDay) as YearMonth, uwd.CST, LaborRoleID, EmployeeTypeID, count(*) as HeadCount, sum(Billed) as Billed, sum(Target) as Target,
  sum(BillableAllocation) as BillableAllocation, sum(ifnull(fa.Hours,0)) as AutobillHours
  from GenomeDW.DUserWorkDay uwd
  left join (
    select UserID, LAST_DAY(YearMonthDay) as YearMonth, sum(Billed) as Billed, sum(ProratedTarget) as Target, 
    max(case when Leave > 0 then 0 else BillableAllocation end) as BillableAllocation
    from GenomeBillability.BillableHours bh
    where EmployeeType in ('Permanent', 'Contractor')
    group by UserID, YearMonth
  ) bh on uwd.YearMonthDay = bh.YearMonth and uwd.UserID = bh.UserID
  left join (
    select fa.Employee as UserID,
      LAST_DAY(ActualDate) as YearMonth,
      sum(fa.Hours) as Hours
      from `genome-datalake-prod.GenomeDW.F_Actuals` fa
        inner join `genome-datalake-prod.GenomeDW.DateDimension` dd on dd.DateDimension = fa.Date
      where fa.Client != 1 and (fa.Oversight != 'None' or fa.SchedulerAssistance != 'None') and dd.Year = 2023
      group by
      fa.Employee, YearMonth
  ) fa on fa.UserID = uwd.UserID and fa.YearMonth = uwd.YearMonthDay
  where uwd.YearMonthDay =  LAST_DAY(uwd.YearMonthDay)
  and EmployeeTypeID in ('PM','CN')
  and uwd.YearMonthDay > date('2015-01-01')
  group by uwd.CST, LaborRoleID, EmployeeTypeID, YearMonth
  order by 1 desc
    """
    rowcount = 0
    for lrhcin in bqclient.query(sql).result():
        if upsert(db.session, LaborRoleHeadcount, {
            'yearmonth': lrhcin.YearMonth,
            'cstname': lrhcin.CST,
            'laborroleid': lrhcin.LaborRoleID,
            'employeetypeid': lrhcin.EmployeeTypeID
        }, 
        { 
            'headcount_eom': lrhcin.HeadCount,  
            'billablealloc_eom': lrhcin.BillableAllocation,
            'billed_hours': lrhcin.Billed,
            'target_hours': lrhcin.Target,
            'autobill_hours': lrhcin.AutobillHours
        }, usecache=True):
            loglines.append(f"Inserted/updated laborrole headcount {lrhcin.YearMonth} {lrhcin.CST} {lrhcin.LaborRoleID} {lrhcin.EmployeeTypeID} {lrhcin.HeadCount}")

        # if this record is from last month, also save it as the headcount for this month
        if lrhcin.YearMonth == datetime.date.today().replace(day=1) - datetime.timedelta(days=1):
            if upsert(db.session, LaborRoleHeadcount, {
                'yearmonth': datetime.date.today().replace(day=1),
                'cstname': lrhcin.CST,
                'laborroleid': lrhcin.LaborRoleID,
                'employeetypeid': lrhcin.EmployeeTypeID
            }, { 
                'headcount_eom': lrhcin.HeadCount,  
                'billablealloc_eom': lrhcin.BillableAllocation,
                'billed_hours': lrhcin.Billed,
                'target_hours': lrhcin.Target,
                'autobill_hours': lrhcin.AutobillHours
            }, usecache=True):
                loglines.append(f"Inserted/updated laborrole headcount {datetime.date.today().replace(day=1)} {lrhcin.CST} {lrhcin.LaborRoleID} {lrhcin.EmployeeTypeID} {lrhcin.HeadCount}")

        rowcount += 1
        if rowcount % 100 == 0:
            db.session.commit()
            loglines.append(f"  {rowcount} rows")

    loglines.append(f"Processed {rowcount} rows")
    db.session.commit()
    return loglines



admin.add_view(DbReplicationView(name='Genome DB', category='DB Replication'))
admin.add_view(BQReplicationView(name='Genome BQ', category='DB Replication'))
