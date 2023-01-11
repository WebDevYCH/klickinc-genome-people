import datetime, json, os, re
from dateutil.relativedelta import relativedelta
import pandas as pd

from flask import render_template, request
from flask_login import login_required
from flask_admin import expose

from core import *
from model import *
from forecasts_core import *

from google.cloud import bigquery
import openpyxl


###################################################################
## ADMIN PAGES AND FORECASTING ALGORITHMS

class ForecastAdminView(AdminBaseView):
    @expose('/')
    def index(self):
        pages = {
            'linear': 'Linear Extrapolation Model',
            'linreg': 'linreg Extrapolation Model',
            'cilinear': 'CI + Linear Extrapolation Model',
            'actuals': 'Actual Hours Billed',
            'gsheets': 'Google Sheets Forecasts Import',
            'lr_hours_day_ratio': 'Labor Role Hours/Day Ratio Import',
            'lr_forecast_sheet': 'Labor Role Forecast Sheet Map Replication',
        }
        return self.render('admin/job_index.html', title="Resource Forecast Processing", pages=pages)

    @expose('/linear')
    def linear(self):
        return self.render('admin/job_log.html', loglines=model_linear())

    @expose('/linreg')
    def linreg(self):
        return self.render('admin/job_log.html', loglines=model_linreg())

    @expose('/cilinear')
    def cilinear(self):
        return self.render('admin/job_log.html', loglines=model_cilinear())

    @expose('/actuals')
    def actuals(self):
        return self.render('admin/job_log.html', loglines=model_actuals())

    @expose('/gsheets')
    def gsheets(self):
        return self.render('admin/job_log.html', loglines=model_gsheets())

    @expose('/lr_hours_day_ratio')
    def lr_hours_day_ratio(self):
        return self.render('admin/job_log.html', loglines=replicate_labor_role_hours_day_ratio())

    @expose('/lr_forecast_sheet')
    def lr_forecast_sheet(self):
        return self.render('admin/job_log.html', loglines=replicate_portfolio_laborrole_forecast_sheet())

@app.cli.command('model_linear')
def model_linear_cmd():
    model_linear()

def model_linear():
    loglines = AdminLog()
    with app.app_context():
        Base.prepare(autoload_with=db.engine, reflect=True)
    loglines.append("Starting Same-Portfolio Linear Extrapolator")
    loglines.append("")

    lookback = 4
    lookahead = 6
    sourcename = 'linear'
    startdate = datetime.date.today().replace(day=1)

    # for each portfolio with forecasts in the next lookahead months
    loglines.append("grabbing portfolio list")
    for p in db.session.query(PortfolioForecast).where(
                PortfolioForecast.yearmonth >= startdate,
                PortfolioForecast.forecast != None,
                PortfolioForecast.forecast != "0.00"
            ).distinct(PortfolioForecast.portfolioid).all():
        loglines.append(f"portfolio {p.portfolioid}")
        # pick up the forecasts from the Genome report (hardcoded numbers come from the report config)
        json = retrieveGenomeReport(2145, [2434,2435,2436], [p.portfolioid,lookback,lookahead])
        loglines.append(f"{json}")

        if 'Entries' in json:
            # for each Genome forecast
            for pfin in json['Entries']:
                # {'AccountPortfolioID': 174, 'YearMonth': '/Date(1669870800000-0500)/', 'Forecast': 54000.0, 'LaborCategory': 'Analytics', 'LaborRoleID': 'ANLTCADR', 'LaborRoleName': 'Analytics, Associate Director', 'PredictedHour': 0.14, 'PredictedAmount': 17.2267}
                pfin['YearMonth'] = parseGenomeDate(pfin['YearMonth'])
                key = f"{pfin['AccountPortfolioID']} // {pfin['YearMonth']} // {pfin['LaborRoleID']} // {sourcename}"

                if pfin['PredictedHour'] != None:
                    pflr = db.session.query(PortfolioLRForecast).filter(
                        PortfolioLRForecast.portfolioid == pfin['AccountPortfolioID'],
                        PortfolioLRForecast.yearmonth == pfin['YearMonth'],
                        PortfolioLRForecast.laborroleid == pfin['LaborRoleID'],
                        PortfolioLRForecast.source == sourcename).first()

                    if pflr != None and pflr.forecastedhours == pfin['PredictedHour']:
                        loglines.append(f"  SKIPPED {key}")
                    else:
                        if pflr != None:
                            loglines.append(f"  UPDATING {key} because not: {pflr.forecastedhours} == {pfin['PredictedHour']} and {pflr.forecasteddollars} == {pfin['PredictedAmount']}")
                        else:
                            loglines.append(f"  NEW {key}")
                            pflr = PortfolioLRForecast()
                            db.session.add(pflr)

                        # set the fields
                        pflr.portfolioid = pfin['AccountPortfolioID']
                        pflr.yearmonth = pfin['YearMonth']
                        pflr.laborroleid = pfin['LaborRoleID']
                        pflr.source = sourcename
                        pflr.userid = None
                        pflr.updateddate = datetime.date.today()
                        pflr.forecasteddollars = pfin['PredictedAmount']
                        pflr.forecastedhours = pfin['PredictedHour']
        else:
            loglines.append("ERROR: CRASH RETRIEVING PORTFOLIO'S FORECASTS")

        db.session.commit()

    return loglines

@app.cli.command('model_linreg')
def model_linreg_cmd():
    model_linreg()

def model_linreg():
    loglines = AdminLog()
    with app.app_context():
        Base.prepare(autoload_with=db.engine, reflect=True)
    loglines.append("Starting Same-Portfolio Linear Regression Extrapolator")
    loglines.append("")

    sourcename = 'linreg'
    # start Jan 1 last year, running for each month since then until now, then extrapolate forward 
    startdate = datetime.date.today().replace(day=1, month=1) - datetime.timedelta(years=1)

    while startdate < datetime.date.today():
        loglines.append(f"processing {startdate}")

    # for each portfolio with forecasts in the next lookahead months
    loglines.append("grabbing portfolio list")
    for p in db.session.query(PortfolioForecast).where(
                PortfolioForecast.yearmonth >= startdate,
                PortfolioForecast.forecast != None,
                PortfolioForecast.forecast != "0.00"
            ).distinct(PortfolioForecast.portfolioid).all():
        loglines.append(f"portfolio {p.portfolioid}")
        # pick up the forecasts from the Genome report (hardcoded numbers come from the report config)
        json = retrieveGenomeReport(2161, [2434], [p.portfolioid])
        loglines.append(f"{json}")

        if 'Entries' in json:
            # for each Genome forecast
            for pfin in json['Entries']:
                # {'AccountPortfolioID': 174, 'YearMonth': '/Date(1669870800000-0500)/', 'Forecast': 54000.0, 'LaborCategory': 'Analytics', 'LaborRoleID': 'ANLTCADR', 'LaborRoleName': 'Analytics, Associate Director', 'PredictedHour': 0.14, 'PredictedAmount': 17.2267}
                pfin['YearMonth'] = parseGenomeDate(pfin['YearMonth'])
                key = f"{pfin['AccountPortfolioID']} // {pfin['YearMonth']} // {pfin['LaborRoleID']} // {sourcename}"

                if pfin['PredictedHour'] != None:
                    pflr = db.session.query(PortfolioLRForecast).filter(
                        PortfolioLRForecast.portfolioid == pfin['AccountPortfolioID'],
                        PortfolioLRForecast.yearmonth == pfin['YearMonth'],
                        PortfolioLRForecast.laborroleid == pfin['LaborRoleID'],
                        PortfolioLRForecast.source == sourcename).first()

                    if pflr != None and pflr.forecastedhours == pfin['PredictedHour']:
                        loglines.append(f"  SKIPPED {key}")
                    else:
                        if pflr != None:
                            loglines.append(f"  UPDATING {key} because not: {pflr.forecastedhours} == {pfin['PredictedHour']} and {pflr.forecasteddollars} == {pfin['PredictedAmount']}")
                        else:
                            loglines.append(f"  NEW {key}")
                            pflr = PortfolioLRForecast()
                            db.session.add(pflr)

                        # set the fields
                        pflr.portfolioid = pfin['AccountPortfolioID']
                        pflr.yearmonth = pfin['YearMonth']
                        pflr.laborroleid = pfin['LaborRoleID']
                        pflr.source = sourcename
                        pflr.userid = None
                        pflr.updateddate = datetime.date.today()
                        pflr.forecasteddollars = pfin['PredictedAmount']
                        pflr.forecastedhours = pfin['PredictedHour']
        else:
            loglines.append("ERROR: CRASH RETRIEVING PORTFOLIO'S FORECASTS")

        db.session.commit()

    return loglines

@app.cli.command('model_cilinear')
def model_cilinear_cmd():
    model_cilinear()

def model_cilinear():
    loglines = AdminLog()
    with app.app_context():
        Base.prepare(autoload_with=db.engine, reflect=True)
    loglines.append("Starting CI-Selected-Portfolio Linear Extrapolator")
    loglines.append("")

    lookahead = 4
    sourcename = 'cilinear'
    startdate = datetime.date.today().replace(day=1)
    enddate = startdate + relativedelta(months=lookahead)

    # gather the labor rates
    loglines.append("gathering labor rates")
    rates = get_clrrates()

    loglines.append("querying Genome BQ model")
    # query the CI-selected portfolios view in BigQuery
    # query returns AccountPortfolioID, LaborRoleID, Pct, CST, Client
    client = bigquery.Client()
    query_job = client.query("SELECT * FROM `genome-datalake-prod.GenomeReports.vDemandPlanningByPortfolio`")
    results = query_job.result()
    # convert the results to a dictionary by portfolio ID with an array of labor role IDs and percentages 
    ciportfolios = {}
    for row in results:
        ciportfolios[row['AccountPortfolioID']] = ciportfolios.get(row['AccountPortfolioID']) or []
        ciportfolios[row['AccountPortfolioID']].append(row)

    # grab each future forecast
    loglines.append("grabbing portfolio forecast list")
    # for each future forecast
    for pf in db.session.query(PortfolioForecast).where(
                PortfolioForecast.yearmonth >= startdate,
                PortfolioForecast.yearmonth < enddate,
            ).join(Portfolio).all():
        loglines.append(f"portfolio {pf.portfolioid} forecast at {pf.yearmonth}, {pf.forecast}")

        # delete existing portfolio labor role forecasts
        db.session.query(PortfolioLRForecast).filter(
            PortfolioLRForecast.portfolioid == pf.portfolioid,
            PortfolioLRForecast.yearmonth == pf.yearmonth,
            PortfolioLRForecast.source == sourcename).delete()

        # if the portfolio is in the CI-selected portfolios and has a forecast
        if pf.portfolioid in ciportfolios and pf.forecast != None and pf.forecast != '$0.00':
            # convert forecast to a number
            pfforecast = float(pf.forecast.replace('$','').replace(',',''))
            # for each labor role in the model forecast
            for cipflr in ciportfolios[pf.portfolioid]:
                # create a record with calculated hours in the portfolio labor role forecast
                pflr = PortfolioLRForecast()
                pflr.portfolioid = pf.portfolioid
                pflr.yearmonth = pf.yearmonth
                pflr.laborroleid = cipflr['LaborRoleID']
                pflr.forecasteddollars = pfforecast * cipflr['Pct'] #/ 100
                pflr.forecastedhours = pflr.forecasteddollars / rates[pf.portfolio.clientname][pflr.laborroleid]
                pflr.source = sourcename
                pflr.updateddate = datetime.date.today()
                db.session.add(pflr)
                loglines.append(f"  {pflr.laborroleid} {pflr.forecastedhours} hours")

        db.session.commit()

    return loglines

@app.cli.command('model_actuals')
def model_actuals_cmd():
    model_actuals()

def model_actuals():
    loglines = AdminLog()
    with app.app_context():
        Base.prepare(autoload_with=db.engine, reflect=True)
    loglines.append("Starting Historical Actuals")
    loglines.append("")

    sourcename = 'actuals'
    startyear = datetime.date.today().year - 2

    loglines.append("querying Genome BQ model")
    # query the CI-selected portfolios view in BigQuery
    # query returns AccountPortfolioID, LaborRoleID, Pct, CST, Client
    client = bigquery.Client()
    query_job = client.query(f"""
    SELECT distinct 
    p.AccountPortfolioID, fact.LaborRole, d.Year, d.Month, 
    sum(fact.Hours) as Hours, sum(fact.ExternalValueDollars) as Dollars

    FROM `genome-datalake-prod.GenomeDW.F_Actuals` fact
    inner join `genome-datalake-prod.GenomeDW.Employee` e on fact.employee=e.employee
    inner join `genome-datalake-prod.GenomeDW.Portfolio` p on fact.portfolio=p.portfolio
    inner join `genome-datalake-prod.GenomeDW.DateDimension` d on fact.Date=d.DateDimension
    inner join `genome-datalake-prod.GenomeDW.Project` pr on fact.project=pr.project
    where year >= {startyear} and pr.Billable=true and fact.LaborRole != 'None'
    group by
    p.AccountPortfolioID, fact.LaborRole, d.Year, d.Month
    """)
    results = query_job.result()

    rowcount = 0
    for inrow in results:
        outrow = db.session.query(PortfolioLRForecast).filter(
            PortfolioLRForecast.portfolioid == inrow['AccountPortfolioID'],
            PortfolioLRForecast.yearmonth == datetime.date(inrow['Year'], inrow['Month'], 1),
            PortfolioLRForecast.laborroleid == inrow['LaborRole'],
            PortfolioLRForecast.source == sourcename).first()
        if outrow == None:
            loglines.append(f"NEW portfolio {inrow['AccountPortfolioID']} labor role {inrow['LaborRole']} {inrow['Hours']} hours in {inrow['Year']}-{inrow['Month']}")
            outrow = PortfolioLRForecast()
            outrow.portfolioid = inrow['AccountPortfolioID']
            outrow.yearmonth = datetime.date(inrow['Year'], inrow['Month'], 1)
            outrow.laborroleid = inrow['LaborRole']
            outrow.source = sourcename
            outrow.forecastedhours = inrow['Hours']
            outrow.forecasteddollars = inrow['Dollars']
            outrow.updateddate = datetime.date.today()
            db.session.add(outrow)
        elif outrow.forecastedhours != inrow['Hours']:
            loglines.append(f"UPD portfolio {inrow['AccountPortfolioID']} labor role {inrow['LaborRole']} {inrow['Hours']} hours in {inrow['Year']}-{inrow['Month']}")
            outrow.forecastedhours = inrow['Hours']
            outrow.forecasteddollars = inrow['Dollars']
            outrow.updateddate = datetime.date.today()
        #else:
            #loglines.append(f"SKP portfolio {inrow['AccountPortfolioID']} labor role {inrow['LaborRole']} {inrow['Hours']} hours in {inrow['Year']}-{inrow['Month']}")

        rowcount += 1
        if rowcount % 100 == 0:
            db.session.commit()

    db.session.commit()

    return loglines

@app.cli.command('model_gsheets')
def model_gsheets_cmd():
    model_gsheets()

def model_gsheets():
    loglines = AdminLog()
    with app.app_context():
        Base.prepare(autoload_with=db.engine, reflect=True)
    loglines.append("Starting Google Sheets Forecast Importer")
    loglines.append("")

    thisyear = datetime.date.today().year
    if datetime.date.today().month > 10:
        thisyear += 1

    source = 'gsheet'

    # gather some lookup data
    loglines.append("gathering lookup data")
    #rates = get_clrrates()
    #laborroles = db.session.query(LaborRole).all()

    # for each Google Sheet forecast
    for gs in db.session.query(PortfolioLRForecastSheet).filter(
        PortfolioLRForecastSheet.year >= thisyear,
        PortfolioLRForecastSheet.gsheet_url != None,
        PortfolioLRForecastSheet.gsheet_url != '',
        PortfolioLRForecastSheet.tabname != None,
        PortfolioLRForecastSheet.tabname != ''
    ).order_by(PortfolioLRForecastSheet.gsheet_url,PortfolioLRForecastSheet.tabname).all():

        # get the sheet with gspread
        loglines.append(f"for portfolio {gs.portfolioid}, getting sheet {gs.gsheet_url}")
        sheet = getGoogleSheet(gs.gsheet_url)

        # get the worksheet and convert to a dataframe for speed
        loglines.append(f"for portfolio {gs.portfolioid}, getting worksheet {gs.tabname}")
        worksheet = sheet.worksheet(gs.tabname)
        df = pd.DataFrame(worksheet.get_all_values())

        # delete any existing plr forecasts for this portfolio in this record's year
        loglines.append(f"for portfolio {gs.portfolioid}, deleting existing forecasts")
        db.session.query(PortfolioLRForecast).filter(
            PortfolioLRForecast.portfolioid == gs.portfolioid,
            PortfolioLRForecast.yearmonth >= datetime.date(gs.year, 1, 1),
            PortfolioLRForecast.yearmonth < datetime.date(gs.year+1, 1, 1),
            PortfolioLRForecast.source == source).delete(synchronize_session='fetch')

        # the sheet has plr forecasts starting in row 15, with laborroleid in col 0
        # forecasted hours are in columns for each month based on the weeks in them: 8=Jan, 13=Feb, 18=Mar, 
        # for each row in the sheet starting at row 15
        loglines.append(f"for portfolio {gs.portfolioid}, processing rows")
        monthcols = {1:8,2:13,3:18,4:24,5:29,6:35,7:40,8:45,9:51,10:56,11:61,12:67}
        for index, row in df.iterrows():
            # if the row is >=14 and has a labor role ID
            if index >= 14 and row[0] != None and row[0] != '':
                # for each month in the year
                for month in range(1,13):
                    monthcol = monthcols[month]
                    # if the month's forecasted hours is not blank
                    if row[monthcol] != None and row[monthcol] != '' and row[monthcol] != '0':
                        # create a record with the forecasted hours and dollars
                        pflr = PortfolioLRForecast()
                        pflr.portfolioid = gs.portfolioid
                        pflr.yearmonth = datetime.date(gs.year, month, 1)
                        pflr.laborroleid = row[0]
                        pflr.forecastedhours = row[monthcol]
                        pflr.forecasteddollars = re.sub(r'[^0-9.]', '', row[monthcol+2])
                        pflr.source = source
                        pflr.updateddate = datetime.date.today()
                        db.session.add(pflr)
                        loglines.append(f"  {pflr.laborroleid} {pflr.forecastedhours} hours at ${pflr.forecasteddollars} in {pflr.yearmonth}")
                        if index % 100 == 0:
                            db.session.commit()

        db.session.commit()

    return loglines



# replicate portfolio list to gsheet mapping table (i.e. create empty records for each portfolio)
@app.cli.command('replicate_portfolio_laborrole_forecast_sheet')
def replicate_portfolio_laborrole_forecast_sheet_cmd():
    replicate_portfolio_laborrole_forecast_sheet()

def replicate_portfolio_laborrole_forecast_sheet():
    loglines = AdminLog()
    loglines.append(f"REPLICATING PORTFOLIO LABOR ROLE FORECAST SHEET")
    with app.app_context():
        Base.prepare(autoload_with=db.engine, reflect=True)

    thisyear = datetime.date.today().year

    # replicate from portfolio table to portfolio labor role forecast sheet
    loglines.append(f"  replicating from portfolio table to portfolio labor role forecast sheet")
    for pin in db.session.query(Portfolio).all():
        pout = db.session.query(PortfolioLRForecastSheet).filter(
            PortfolioLRForecastSheet.portfolioid == pin.id,
            PortfolioLRForecastSheet.year == thisyear
            ).first()
        if pout == None:
            pout = PortfolioLRForecastSheet()
            pout.portfolioid = pin.id
            pout.year = thisyear
            db.session.add(pout)
        # fields gsheet_url and tabname are left null
    db.session.commit()

    loglines.append(f"  done")
    return loglines


@app.cli.command('replicate_labor_role_hours_day_ratio')
def replicate_labor_role_hours_day_ratio_cmd():
    replicate_labor_role_hours_day_ratio()

def replicate_labor_role_hours_day_ratio():
    loglines = AdminLog()
    loglines.append(f"REPLICATING LABOR ROLE HOURS/DAY RATIO")
    with app.app_context():
        Base.prepare(autoload_with=db.engine, reflect=True)
    # run query against Genome datalake in BQ
    loglines.append(f"  running query")
    client = bigquery.Client()
    query_job = client.query("""
select LaborRoleID, LaborRole, avg(Hours) / round(avg(HeadCount),2) as HoursPerDay, round(avg(HeadCount),2) as HeadCount
from (
  select uwd.YearMonthDay, uwd.LaborRoleID, uwd.LaborRole, sum(Hours) as Hours, sum(HeadCount) as HeadCount
  from 
  (
    select uwd.YearMonthDay, uwd.LaborRoleID, uwd.LaborRole, count(distinct UserID) as HeadCount
    from GenomeDW.DUserWorkDay uwd 
    where uwd.EmployeeTypeID = 'PM' --and uwd.YearMonthDay = '2022-08-19' and uwd.LaborRoleID = 'CLSRVDIR'
		and uwd.BillablePercent >= 0.5
		and uwd.IsAtWork = true and uwd.IsActive = true
    group by uwd.YearMonthDay, uwd.LaborRoleID, uwd.LaborRole
  ) uwd 
  inner join 
  (
    select cast(fa.ActualDateTime as date) as YearMonthDay, sum(fa.Hours) as Hours, fa.LaborRole
    from `genome-datalake-prod.GenomeDW.F_Actuals` fa
    inner join `genome-datalake-prod.GenomeDW.DUser` u on fa.Employee = u.UserID
    inner join `genome-datalake-prod.GenomeDW.Project` p on fa.Project = p.Project
    where u.EmployeeTypeID = 'PM'
    and fa.ActualDateTime >= cast(date_sub(current_date('EST5EDT'), INTERVAL 4 MONTH) AS TIMESTAMP)
		and p.billable=true
    group by fa.LaborRole, cast(fa.ActualDateTime as date)
  ) a on uwd.YearMonthDay = cast(a.YearMonthDay as date) and uwd.LaborRoleID = a.LaborRole
  where extract(dayofweek from uwd.YearMonthDay) between 2 and 6
  group by uwd.YearMonthDay, uwd.LaborRoleID, uwd.LaborRole
) a
group by LaborRoleID, LaborRole
order by HoursPerDay desc
    """)
    results = query_job.result()

    # for each row in the results, update the database
    for row in results:
        ratio = db.session.query(LaborRoleHoursDayRatio).filter(LaborRoleHoursDayRatio.laborroleid == row.LaborRoleID).first()
        if ratio == None:
            loglines.append(f"  adding {row.LaborRole}")
            ratio = LaborRoleHoursDayRatio()
            db.session.add(ratio)
        else:
            loglines.append(f"  updating {row.LaborRole}")

        ratio.laborroleid = row.LaborRoleID
        ratio.name = row.LaborRole
        ratio.hoursperday = round(row.HoursPerDay,2)
        ratio.headcount = round(row.HeadCount,2)

    loglines.append("  committing")
    db.session.commit()
    return loglines



admin.add_view(ForecastAdminView(name='Forecast Processing', category='Forecasts'))



