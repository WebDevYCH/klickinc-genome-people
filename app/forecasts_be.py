import datetime, os, re
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd

from flask_admin import expose
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
import numpy as np

from core import *
from model import *
from forecasts_core import *

from google.cloud import bigquery
from supervised import AutoML
import warnings

#import autosklearn.regression
#from autoPyTorch.api.tabular_classification import TabularClassificationTask
#from autoPyTorch.api.tabular_regression import TabularRegressionTask
#import autoPyTorch.api

explain_model_path = "../cache/automl_lrforecast_explain"
perform_model_path = "../cache/automl_lrforecast_perform"
compete_model_path = "../cache/automl_lrforecast_compete"
optuna_model_path = "../cache/automl_lrforecast_optuna"
bq_csv_path = f"../cache/automl_lrforecast_bq_{datetime.datetime.now().strftime('%Y%m%d')}.csv"
bq_pickle_path = f"../cache/automl_lrforecast_bq_{datetime.datetime.now().strftime('%Y%m%d')}.pkl"


###################################################################
## ADMIN PAGES AND FORECASTING ALGORITHMS

class ForecastAdminView(AdminBaseView):
    @expose('/')
    def index(self):
        pages = {
            'linear': 'Linear Extrapolation Model',
            'linreg': 'Linear Regression Extrapolation Model',
            'cilinear': 'CI + Linear Extrapolation Model',
            'actuals': 'Actual Hours Billed',
            'gsheets': 'Google Sheets Forecasts Import',
            'mljar': 'MLJAR Forecasts Import',
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

    @expose('/mljar')
    def mljar(self):
        return self.render('admin/job_log.html', loglines=model_mljar())

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

    sourcename = 'linear'
    lookbackmonths = 4
    lookaheadmonths = 1
    # start Jan 1 last year, running for each month since then until now, then extrapolate forward 
    today = datetime.date.today()
    startdate = today.replace(day=1, month=1) - relativedelta(years=1)

    while startdate < today:
        rowcount = 0
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
            json = retrieveGenomeReport(2155, [2442,2443,2445,2444], 
                [p.portfolioid,lookbackmonths,f"{startdate.year}-{startdate.month:02d}-01",lookaheadmonths])
            #loglines.append(f"{json}")

            if 'Entries' in json:
                # for each Genome forecast
                for pfin in json['Entries']:
                    # {"AccountPortfolioID":580,"YearMonth":"\/Date(1669870800000-0500)\/","CategoryName":"Analytics","LaborRoleID":"ANLTCSTD","LaborRoleName":"Analytics","PredictedHour":110.67,"ActualHour":159.05,"PredictedHourAccuracy":69.58}
                    upsert(db.session, PortfolioLRForecast, {
                        'portfolioid': pfin['AccountPortfolioID'],
                        'yearmonth': today.replace(year=pfin['Year'], month=pfin['Month'], day=1),
                        'laborroleid': pfin['LaborRoleID'],
                        'source': sourcename,
                    }, {
                        'forecastedhours': pfin['PredictedHour'],
                        'forecasteddollars': pfin['PredictedAmount']
                    })

                    rowcount += 1
                    if rowcount % 100 == 0:
                        loglines.append(f"  updated {rowcount} rows")
                        db.session.commit()
                loglines.append(f"    updated {rowcount} rows")
                db.session.commit()
            else:
                loglines.append("ERROR: CRASH RETRIEVING PORTFOLIO'S FORECASTS")

        loglines.append(f"  updated {rowcount} rows")
        db.session.commit()
        # add 1 month to startdate
        startdate = startdate + relativedelta(months=1)

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
    lookbackmonths = 8
    lookaheadmonths = 4
    # start Jan 1 last year, running for each month since then until now, then extrapolate forward 
    today = datetime.date.today()
    startdate = today.replace(day=1, month=1) - relativedelta(years=1)

    while startdate < today + relativedelta(months=1):
        rowcount = 0
        loglines.append(f"processing {startdate}")

        # for each portfolio with forecasts from start month to one month after now
        # the one after now will predict lookaheadmonths from now
        thislookahead = 1
        if startdate >= today:
            thislookahead = lookaheadmonths

        # for each portfolio with forecasts at this month or later
        for p in db.session.query(PortfolioForecast).where(
                    PortfolioForecast.yearmonth >= startdate,
                    PortfolioForecast.forecast != None,
                    PortfolioForecast.forecast != "0.00"
                ).distinct(PortfolioForecast.portfolioid).all():
            loglines.append(f"  portfolio {p.portfolioid} for {startdate}")
            # pick up the forecasts from the Genome report (hardcoded numbers come from the report config)
            json = retrieveGenomeReport(2161, [2448,2449,2452,2450], 
                [p.portfolioid,lookbackmonths,f"{startdate.year}-{startdate.month:02d}-01",thislookahead])
            #loglines.append(f"{json}")

            if 'Entries' in json:
                # for each Genome forecast
                for pfin in json['Entries']:
                    # {"AccountPortfolioID":580,"YearMonth":"\/Date(1669870800000-0500)\/","CategoryName":"Analytics","LaborRoleID":"ANLTCSTD","LaborRoleName":"Analytics","PredictedHour":110.67,"ActualHour":159.05,"PredictedHourAccuracy":69.58}
                    pfin['YearMonth'] = parseGenomeDate(pfin['YearMonth'])
                    upsert(db.session, PortfolioLRForecast, {
                        'portfolioid': pfin['AccountPortfolioID'],
                        'yearmonth': pfin['YearMonth'],
                        'laborroleid': pfin['LaborRoleID'],
                        'source': sourcename,
                    }, {
                        'forecastedhours': pfin['PredictedHour'],
                        'forecasteddollars': None
                    })

                    rowcount += 1
                    if rowcount % 100 == 0:
                        loglines.append(f"  updated {rowcount} rows")
                        db.session.commit()
                loglines.append(f"    updated {rowcount} rows")
                db.session.commit()
            else:
                loglines.append("ERROR: CRASH RETRIEVING PORTFOLIO'S FORECASTS")

        loglines.append(f"  updated {rowcount} rows")
        db.session.commit()
        # add 1 month to startdate
        startdate = startdate + relativedelta(months=1)


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
        upsert(db.session, PortfolioLRForecast, {
            'portfolioid': inrow['AccountPortfolioID'],
            'yearmonth': datetime.date(inrow['Year'], inrow['Month'], 1),
            'laborroleid': inrow['LaborRole'],
            'source': sourcename,
        }, {
            'actualhours': inrow['Hours'],
            'actualdollars': inrow['Dollars'],
        })

        rowcount += 1
        if rowcount % 100 == 0:
            loglines.append(f"  {rowcount} rows")
            db.session.commit()

    loglines.append(f"  {rowcount} rows")
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

@app.cli.command('model_mljar')
def model_mljar_cmd():
    model_mljar()

def model_mljar():
    loglines = AdminLog()
    with app.app_context():
        Base.prepare(autoload_with=db.engine, reflect=True)
    loglines.append("Starting MLJAR Forecast Importer")
    loglines.append("")

    source = 'mljar'

    warnings.simplefilter(action='ignore', category=FutureWarning)
    warnings.filterwarnings("ignore", category=UserWarning, module="lightgbm",
            message="'verbose_eval' argument is deprecated and will be removed in a future release of LightGBM. Pass 'log_evaluation()' callback via 'callbacks' argument instead.")

    automl = AutoML(mode="Compete", results_path=compete_model_path)
    #automl = AutoML(mode="Optuna", results_path=optuna_model_path)

    # start Jan 1 last year, running for each month since then until now, then extrapolate forward 
    today = datetime.date.today()
    startdate = today.replace(day=1, month=1) - relativedelta(years=1)
    lookaheadmonths = 3

    laborroles = db.session.query(LaborRole).all()

    commitrowcount = 0
    loglines.append(f"processing {startdate}")

    # for each portfolio with forecasts from start month to lookaheadmonths from now
    for pf in db.session.query(PortfolioForecast).filter(
        PortfolioForecast.yearmonth >= startdate,
        PortfolioForecast.yearmonth < startdate + relativedelta(months=lookaheadmonths)
    ).all():
        loglines.append(f"  for portfolio {pf.portfolioid}, processing {pf.yearmonth}")
        starttime = datetime.datetime.now()
        # build a dataframe to predict the hours for this portfolio and month
        # model was trained on feature set:
        #   YearMonth, PDName, GADName, AccountPortfolioID, ClientName, PortfolioName, LaborRole, OfficeName, CIChannel, CILifecycle, CIDeliverable
        #   (CIChannel, CILifecycle, CIDeliverable are string_agg'd together with " // " as the delimiter)
        #   (YearMonth is the year*100+month)
        Xdf = pd.DataFrame(columns=['ID','YearMonth','PDName','GADName','AccountPortfolioID','ClientName','PortfolioName','LaborRole','OfficeName','CIChannel','CILifecycle','CIDeliverable'])
        # for each labor role
        for lr in laborroles:
            # add a row to the dataframe with the portfolio's feature values and the labor role
            Xdf = Xdf.append({
                'ID': f"{pf.portfolioid}-{lr.id}-{pf.yearmonth.year*100 + pf.yearmonth.month}",
                'YearMonth': pf.yearmonth.year*100 + pf.yearmonth.month,
                'PDName': pf.portfolio.currpdname,
                'GADName': pf.portfolio.currgadname,
                'AccountPortfolioID': pf.portfolio.id,
                'ClientName': pf.portfolio.clientname,
                'PortfolioName': pf.portfolio.name,
                'LaborRole': lr.id,
                'OfficeName': pf.portfolio.currofficename,
                'CIChannel': None,
                'CILifecycle': None,
                'CIDeliverable': None,
            }, ignore_index=True)

        # load the model and predict the dataset (returns a numpy.ndarray)
        predictstarttime = datetime.datetime.now()
        predictions = automl.predict(Xdf)
        predictendtime = datetime.datetime.now()

        # for each row in the predictions, create a record in the portfolio labor role forecast table
        rowcount = 0
        for index, row in np.ndenumerate(predictions):
            if row != None and row > 0:
                upsert(db.session, PortfolioLRForecast, {
                    'portfolioid': pf.portfolioid,
                    'yearmonth': pf.yearmonth,
                    'laborroleid': Xdf.loc[index,'LaborRole'],
                    'source': source,
                }, {
                    'forecastedhours': row,
                    'forecasteddollars': None,
                    'updateddate': datetime.date.today()
                }, usecache=True)
                rowcount += 1
                commitrowcount += 1

        if commitrowcount > 1000:
            db.session.commit()
            commitrowcount = 0
        loglines.append(f"    processed {rowcount} rows, took {datetime.datetime.now() - starttime} seconds, predictions took {predictendtime - predictstarttime} seconds")
    
    db.session.commit()




# replicate portfolio list to gsheet mapping table (i.e. create empty records for each portfolio)
@app.cli.command('replicate_portfolio_laborrole_forecast_sheet')
def replicate_portfolio_laborrole_forecast_sheet_cmd():
    replicate_portfolio_laborrole_forecast_sheet()

def replicate_portfolio_laborrole_forecast_sheet():
    loglines = AdminLog()
    loglines.append(f"REPLICATING PORTFOLIO LABOR ROLE FORECAST SHEET FROM PORTFOLIO LIST")
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
        upsert(db.session, LaborRoleHoursDayRatio, {"laborroleid": row.LaborRoleID}, {
            "laborroleid": row.LaborRoleID,
            "name": row.LaborRole,
            "hoursperday": round(row.HoursPerDay,2),
            "headcount": round(row.HeadCount,2)
        })

    loglines.append("  committing")
    db.session.commit()
    return loglines



admin.add_view(ForecastAdminView(name='Forecast Processing', category='Forecasts'))



########################################################################################
# Multivariate Regression Models with AutoML
# training data is from 15 years of actuals, in BigQuery view GenomeDW.vActualsHoursByLRPortfolioMonthForPrediction
# fields are Hours, YearMonth, PDName, GADName, AccountPortfolioID, ClientName, PortfolioName, Laborrole
# Hours is the field I want to predict. the others are feature columns.


# mljar AutoML training
@app.cli.command('train_automl_model')
def train_automl_model_cmd():
    train_automl_model()

def train_automl_model():
    while app.logger.handlers:
        print("FOUND A LOGGER")
        app.logger.handlers.pop()
    loglines = AdminLog()
    loglines.append(f"TRAINING AUTOML MODEL")
    warnings.filterwarnings("ignore", category=FutureWarning, module="supervised")
    warnings.filterwarnings("ignore", category=UserWarning, module="xgboost.core")

    # run query against Genome datalake in BQ, or load from a cache file
    df = None
    if os.path.exists(bq_pickle_path):
        loglines.append(f"  loading from cache")
        df = pd.read_pickle(bq_pickle_path)
    else:
        loglines.append(f"  running query")
        rows = bigquery.Client().query("""
select sum(Hours) as Hours, 
d.Year*100+d.Month as YearMonth,
(p.PDName) as PDName, (p.GADName) as GADName, p.AccountPortfolioID, 
(p.ClientName) as ClientName, (p.Name) as PortfolioName,
(lr.LaborRole) as LaborRole, p.OfficeName,
pf.FEARevenue as RevenueForecastForPortfolioMonth,
string_agg(distinct cic.Name, " // ") as CIChannel,
string_agg(distinct cil.Name, " // ") as CILifecycle,
string_agg(distinct cid.Name, " // ") as CIDeliverable,
from `genome-datalake-prod.GenomeDW.F_Actuals` fact
join `genome-datalake-prod.GenomeDW.Portfolio` p on fact.Portfolio=p.Portfolio
join `genome-datalake-prod.GenomeDW.DateDimension` d on fact.Date=d.DateDimension
join `genome-datalake-prod.GenomeDW.Project` pr on fact.Project=pr.Project
join `genome-datalake-prod.GenomeDW.LaborRole` lr on fact.LaborRole=lr.LaborRole
left outer join `genome-datalake-prod.GenomeReports.Finance_vMAPEEARevenue` pf on p.AccountPortfolioID=pf.AccountPortfolioID and date(pf.YearMonth)=date(d.Year,d.Month,1)
left outer join `genome-datalake-prod.GenomeDW.CIChannelMapping` cicmap on cicmap.ProjectID=pr.ProjectID and date(cicmap.YearMonthDay)=d.Date
left outer join `genome-datalake-prod.GenomeDW.CIChannel` cic on cicmap.InsightID=cic.ID
left outer join `genome-datalake-prod.GenomeDW.CILifecycleMapping` cilmap on cilmap.ProjectID=pr.ProjectID and date(cilmap.YearMonthDay)=d.Date
left outer join `genome-datalake-prod.GenomeDW.CILifecycle` cil on cilmap.InsightID=cil.ID
left outer join `genome-datalake-prod.GenomeDW.CIDeliverableMapping` cidmap on cidmap.ProjectID=pr.ProjectID and date(cidmap.YearMonthDay)=d.Date
left outer join `genome-datalake-prod.GenomeDW.CIDeliverable` cid on cidmap.InsightID=cid.ID
where pr.Billable=true
group by d.Year, d.Month,
p.PDName, p.GADName, p.AccountPortfolioID, p.ClientName, p.Name,
lr.LaborRole, p.OfficeName, pf.FEARevenue
""").result()
        loglines.append(f"  results rows {rows.total_rows}")
        df = rows.to_dataframe()
        df.to_csv(bq_csv_path)
        df.to_pickle(bq_pickle_path)

    # split into train and test
    loglines.append(f"  splitting into train and test")
    X_train, X_test, y_train, y_test = train_test_split(
        df.drop("Hours", axis=1),
        df["Hours"],
        test_size=0.2,
        random_state=123,
    )
    loglines.append(f"  training with rows {X_train.shape[0]} test rows {X_test.shape[0]}")

    # train models with Explain settings
    trainloadstart = time.time()
    automl = AutoML(mode="Explain", results_path=explain_model_path)
    automl.fit(X_train, y_train)
    trainloadend = time.time()
    # compute the MSE on test data
    starttime = time.time()
    predictions = automl.predict(X_test)
    rmsescore = mean_squared_error(y_test, predictions, squared=False)
    r2score = r2_score(y_test, predictions)
    stddev = np.std(y_test)
    loglines.append(f"Explain scores: RMSE={rmsescore} RMSE/stddev={rmsescore/stddev} R2={r2score} time={time.time()-starttime} trainloadtime={trainloadend-trainloadstart}")

    # train models with Perform settings
    trainloadstart = time.time()
    automl = AutoML(mode="Perform", results_path=perform_model_path)
    automl.fit(X_train, y_train)
    trainloadend = time.time()
    # compute the RMSE on test data
    starttime = time.time()
    predictions = automl.predict(X_test)
    rmsescore = mean_squared_error(y_test, predictions, squared=False)
    r2score = r2_score(y_test, predictions)
    stddev = np.std(y_test)
    loglines.append(f"Perform scores: RMSE={rmsescore} RMSE/stddev={rmsescore/stddev} R2={r2score} time={time.time()-starttime} trainloadtime={trainloadend-trainloadstart}")

    # train models with Compete settings
    trainloadstart = time.time()
    automl = AutoML(mode="Compete", results_path=compete_model_path)
    automl.fit(X_train, y_train)
    trainloadend = time.time()
    # compute the RMSE on test data
    starttime = time.time()
    predictions = automl.predict(X_test)
    rmsescore = mean_squared_error(y_test, predictions, squared=False)
    r2score = r2_score(y_test, predictions)
    stddev = np.std(y_test)
    loglines.append(f"Compete scores: RMSE={rmsescore} RMSE/stddev={rmsescore/stddev} R2={r2score} time={time.time()-starttime} trainloadtime={trainloadend-trainloadstart}")

    # train models with Optuna settings
    trainloadstart = time.time()
    automl = AutoML(mode="Optuna", results_path=optuna_model_path, optuna_time_budget=3600)
    automl.fit(X_train, y_train)
    trainloadend = time.time()
    # compute the RMSE on test data
    starttime = time.time()
    predictions = automl.predict(X_test)
    rmsescore = mean_squared_error(y_test, predictions, squared=False)
    r2score = r2_score(y_test, predictions)
    stddev = np.std(y_test)
    loglines.append(f"Optuna scores: RMSE={rmsescore} RMSE/stddev={rmsescore/stddev} R2={r2score} time={time.time()-starttime} trainloadtime={trainloadend-trainloadstart}")
    
    loglines.append("  done")
    return loglines

