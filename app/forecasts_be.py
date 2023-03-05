import asyncio
import datetime, os, re
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd

from flask_admin import expose
from sklearn.metrics import mean_squared_error, r2_score
import numpy as np

from core import *
from model import *
from forecasts_core import *

from google.cloud import bigquery

try:
    from supervised import AutoML
except:
    pass
from fbprophet import Prophet
    
import warnings
pd.options.mode.chained_assignment = None  # default='warn'
warnings.filterwarnings("ignore", message="The frame.append method is deprecated")


explain_model_path = "../cache/automl_lrforecast_explain"
perform_model_path = "../cache/automl_lrforecast_perform"
compete_model_path = "../cache/automl_lrforecast_compete"
optuna_model_path = "../cache/automl_lrforecast_optuna"
bq_csv_path = f"../cache/automl_lrforecast_bq_{datetime.datetime.now().strftime('%Y%m%d')}.csv"
bq_pickle_path = f"../cache/automl_lrforecast_bq_{datetime.datetime.now().strftime('%Y%m%d')}.pkl"

automl_query = """
select sum(Hours) as Hours, 
d.Year*100+d.Month as YearMonth,
(p.PDName) as PDName, (p.GADName) as GADName, p.AccountPortfolioID, 
(p.ClientName) as ClientName, (p.Name) as PortfolioName,
p.CST as CSTName,
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
p.CST,
lr.LaborRole, p.OfficeName, pf.FEARevenue
"""


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

    # start Jan 1 last year, running for each month since then until now, then extrapolate forward 
    today = datetime.date.today()

    for lookbackmonths in [4,8,10,12,16]:
        startdate = today.replace(day=1, month=1) - relativedelta(years=1)

        #startdate = datetime.date(2022,11,1)

        sourcename = f'linear{lookbackmonths}'
        lookaheadmonths = 12
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
                        # ridiculousness test
                        if pfin['PredictedHour'] >= 0:
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

    for lookbackmonths in [4,8,10,12,16]:
        sourcename = f'linreg{lookbackmonths}'
        lookaheadmonths = 12
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
                try:
                    json = retrieveGenomeReport(2161, [2448,2449,2452,2450], 
                        [p.portfolioid,lookbackmonths,f"{startdate.year}-{startdate.month:02d}-01",thislookahead])
                except Exception as e:
                    loglines.append(f"ERROR: EXCEPTION RETRIEVING PORTFOLIO'S FORECASTS")
                    continue
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

@app.cli.command('model_prophet')
def model_prophet_cmd():
    model_prophet()

def model_prophet():
    loglines = AdminLog()
    with app.app_context():
        Base.prepare(autoload_with=db.engine, reflect=True)
    loglines.append("Starting Prophet Extrapolator")
    loglines.append("")

    sourcename = f'prophet'
    lookaheadmonths = 12
    lookbackyear = 2012
    thisyear = datetime.date.today().year
    lastyear = thisyear - 1
    thismonth = datetime.date.today().month

    # for each portfolio with any forecasts this year or last year
    for p in db.session.query(PortfolioForecast).where(
                PortfolioForecast.yearmonth >= datetime.date(lastyear,1,1),
                PortfolioForecast.forecast != None,
                PortfolioForecast.forecast != "0.00"
            ).distinct(PortfolioForecast.portfolioid).all():
        loglines.append(f"  portfolio {p.portfolioid}")

        # pick up all actuals for this portfolio starting in lookbackyear
        query = f"""
        select 
        d.ActualDate as ds,
        sum(Hours) as y,
        lr.LaborRole as laborrole
        from `genome-datalake-prod.GenomeDW.F_Actuals` fact
        join `genome-datalake-prod.GenomeDW.Portfolio` p on fact.Portfolio=p.Portfolio
        join `genome-datalake-prod.GenomeDW.DateDimension` d on fact.Date=d.DateDimension
        join `genome-datalake-prod.GenomeDW.Project` pr on fact.Project=pr.Project
        join `genome-datalake-prod.GenomeDW.LaborRole` lr on fact.LaborRole=lr.LaborRole
        join `genome-datalake-prod.GenomeDW.JobFunction` jf on fact.JobFunction=jf.JobFunction
        where pr.Billable=true
        and d.ActualDate >= '{lookbackyear}-01-01'
        and p.AccountPortfolioID = {p.portfolioid}
        and lr.LaborRole != 'None'
        group by 
        d.ActualDate, lr.LaborRole
        """

        #os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "../keys/google-key.json"
        bqresult = bigquery.Client().query(query)
        # convert to dataframe with date as index, do other cleanup
        df = bqresult.to_dataframe()
        df['ds'] = pd.to_datetime(df['ds'])
        df = df.set_index('ds')
        df = df.sort_index()
        df['ds'] = df.index
        df['yhat'] = np.nan
        df['yhat_upper'] = np.nan
        df['yhat_lower'] = np.nan
        df['floor'] = 0

        # for each labor role in df
        for lr in df['laborrole'].unique():

            rowcount = 0

            # for each month starting in Jan of last year
            #for y in range(lastyear,thisyear+1):
            for y in [thisyear]:
                for m in range(1,13):
                    if y == thisyear and m > datetime.date.today().month:
                        break
                    startofrowmonth = datetime.date(y,m,1)
                    startofnextmonth = startofrowmonth + relativedelta(months=1)

                    loglines.append(f"    training/predicting {p.portfolioid} {lr} {startofrowmonth} - {startofnextmonth}")

                    # gather records in df not including this month
                    train = df.loc[(df['laborrole'] == lr) & (df.index < pd.to_datetime(startofrowmonth))]

                    # skip months with almost no data
                    if len(train['y']) < 3:
                        loglines.append(f"      skipping month with {train['y'].sum()} hours")
                        continue

                    # create and train the model (hardcoded hyperparameters, tuned with the forecasts_prophet.py script)
                    model = Prophet(
                        growth='linear',
                        changepoint_range=0.99,
                        changepoint_prior_scale=0.2,
                        seasonality_mode='multiplicative',
                    )
                    model.add_country_holidays(country_name='CA')
                    model.fit(train)

                    # predict past the sample, for 1 month or the rest of the year depending on whether we're in the this month
                    future = model.make_future_dataframe(periods=365, include_history=False)
                    future['floor'] = 0
                    forecast = model.predict(future)

                    # fill in just the current row's month's forecast
                    # unless row month is this month, in which case fill in the rest of the year
                    endofstoragemonth = startofrowmonth + relativedelta(months=lookaheadmonths)
                    if startofrowmonth == datetime.date(thisyear,thismonth,1):
                        endofstoragemonth = datetime.date(thisyear,12,1)

                    for storagemonth in pd.date_range(startofrowmonth, endofstoragemonth, freq='MS'):
                        # sum total forecasted hours for the row's month
                        hours = forecast[(forecast['ds'] >= pd.to_datetime(storagemonth)) & (forecast['ds'] < pd.to_datetime(storagemonth + relativedelta(months=1)))]['yhat'].sum()
                        # save the forecast to the database
                        loglines.append(f"    storing {p.portfolioid} {lr} {storagemonth} --> {hours}")
                        upsert(db.session, PortfolioLRForecast, {
                            'portfolioid': p.portfolioid,
                            'yearmonth': storagemonth,
                            'laborroleid': lr,
                            'source': sourcename,
                        }, {
                            'forecastedhours': hours,
                            'forecasteddollars': None
                        })
                        rowcount += 1


            loglines.append(f"    saved {rowcount} rows")
            db.session.commit()
        db.session.commit()
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

    lookahead = 12
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

# blend multiple models together
@app.cli.command('model_blend')
def model_blend_cmd():
    model_blend()

def model_blend():
    loglines = AdminLog()
    with app.app_context():
        Base.prepare(autoload_with=db.engine, reflect=True)
    loglines.append("Starting Multi-Model Blends")
    loglines.append("")

    blends = {
        'blend1': {
            'models': ['gsheet','linear4','linear8','linreg8'],
        },
        'blend2': {
            'models': ['gsheet','linear4','linear8','linreg8','linreg10'],
        },
        'blend3': {
            'models': ['gsheet','linear4','linear8','linreg8','linreg10','cilinear'],
        },
        'blendm1': {
            'models': ['linear4','linear8','linreg8','linreg10','cilinear'],
        },
        'blendm2': {
            'models': ['linear4','linear8','linreg8','linreg10'],
        },
        'blendm3': {
            'models': ['linear4','linear8','linreg8','linreg10','cilinear'],
        },
    }

    for blend in blends.keys():
        lookaheadmonths = 12

        # start Jan 1 last year, running for each month since then until now, then extrapolate forward 
        today = datetime.date.today()
        startdate = today.replace(day=1, month=1) - relativedelta(years=1)

        while startdate < today + relativedelta(months=lookaheadmonths):
            rowcount = 0
            loglines.append(f"processing {blend} for {startdate}")

            # gather the list of forecasts for this month and save in a hash by portfolio ID and labor role and source
            forecastedhours = {}
            forecastedpflrs = {}
            loglines.append("  gathering portfolio forecast list")
            for plrf in db.session.query(PortfolioLRForecast).where(
                        PortfolioLRForecast.yearmonth == startdate,
                        PortfolioLRForecast.forecastedhours != None,
                        PortfolioLRForecast.forecastedhours != 0
                    ).all():
                fhkey = f"{plrf.portfolioid}-{plrf.laborroleid}-{plrf.source}"
                forecastedhours[fhkey] = plrf.forecastedhours
                fkey = f"{plrf.portfolioid}-{plrf.laborroleid}"
                forecastedpflrs[fkey] = True


            try:
                rowcount = 0
                # for each portfolio-laborrole combination with a forecast
                for fkey in forecastedpflrs.keys():
                    modelcount = 0
                    modelhours = 0
                    # for each model in the blend
                    for model in blends[blend]['models']:
                        # if there is a forecast for this portfolio-laborrole-model combination
                        fhkey = f"{fkey}-{model}"
                        if fhkey in forecastedhours:
                            # add the forecast to the blend
                            modelcount += 1
                            modelhours += forecastedhours[fhkey]
                    if modelcount > 0:
                        #loglines.append(f"    {blend} {startdate} {fkey}: found {modelcount} models, {modelhours} hours --> {modelhours / modelcount} hours")
                        # calculate the average hours for the blend
                        blendhours = modelhours / len(blends[blend]['models'])
                        upsert(db.session, PortfolioLRForecast, {
                            'portfolioid': fkey.split('-')[0],
                            'yearmonth': startdate,
                            'laborroleid': fkey.split('-')[1],
                            'source': blend,
                        }, {
                            'forecastedhours': blendhours,
                            'updateddate': datetime.date.today(),
                        })
                        rowcount += 1
                        if rowcount % 100 == 0:
                            loglines.append(f"    {rowcount} rows")
                            db.session.commit()
                loglines.append(f"    {rowcount} rows")
                db.session.commit()
                
                
            except Exception as e:
                loglines.append(f"ERROR: {e}")
                handle_ex(e)

            # add 1 month to startdate
            startdate = startdate + relativedelta(months=1)


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
    thismonth = datetime.date.today().month

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
    where year >= {startyear} and month < {thismonth} and pr.Billable=true and fact.LaborRole != 'None'
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
            'forecastedhours': inrow['Hours'],
            'forecasteddollars': inrow['Dollars'],
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
    asyncio.run(model_gsheets())

async def model_gsheets():
    loglines = AdminLog()
    with app.app_context():
        Base.prepare(autoload_with=db.engine, reflect=True)
    loglines.append("Starting Google Sheets Forecast Importer")
    loglines.append("")

    thisyear = datetime.date.today().year
    if datetime.date.today().month > 10:
        thisyear += 1

    source = 'gsheet'

    # delete existing gsheet records, in case a portfolio got disconnected
    loglines.append(f"deleting existing forecasts")
    db.session.query(PortfolioLRForecast).filter(
        PortfolioLRForecast.yearmonth >= datetime.date(thisyear, 1, 1),
        PortfolioLRForecast.yearmonth < datetime.date(thisyear+1, 1, 1),
        PortfolioLRForecast.source == source).delete(synchronize_session='fetch')

    loglines.append("gathering labor role forecasts")
    pfforecastsheets = db.session.query(PortfolioLRForecastSheet).filter(
        PortfolioLRForecastSheet.year >= thisyear,
        PortfolioLRForecastSheet.gsheet_url != None,
        PortfolioLRForecastSheet.gsheet_url != '',
        PortfolioLRForecastSheet.gsheet_url != 'a url',
        PortfolioLRForecastSheet.tabname != None,
        PortfolioLRForecastSheet.tabname != ''
    ).order_by(PortfolioLRForecastSheet.gsheet_url,PortfolioLRForecastSheet.tabname).all()

    # for check each mapping to make sure we can reference the sheet+tab
    for pfforecastsheet in pfforecastsheets:
        loglines.append(f"for portfolio {pfforecastsheet.portfolioid}, getting sheet {pfforecastsheet.gsheet_url}")
        sheet = getGoogleSheet(pfforecastsheet.gsheet_url)
        loglines.append(f"  getting worksheet {pfforecastsheet.tabname}")
        worksheet = sheet.worksheet(pfforecastsheet.tabname)
        await asyncio.sleep(1)

    # for each Google Sheet forecast
    for pfforecastsheet in pfforecastsheets:

        loglines.append(f"for portfolio {pfforecastsheet.portfolioid}, getting sheet {pfforecastsheet.gsheet_url}")
        sheet = getGoogleSheet(pfforecastsheet.gsheet_url)
        loglines.append(f"  getting worksheet {pfforecastsheet.tabname}")
        worksheet = sheet.worksheet(pfforecastsheet.tabname)

        df = pd.DataFrame(worksheet.get_all_values())

        # the sheet has plr forecasts starting in row 15, with laborroleid in col 0
        # forecasted hours are in columns for each month based on the weeks in them: 8=Jan, 13=Feb, 18=Mar, 
        # for each row in the sheet starting at row 15
        loglines.append(f"for portfolio {pfforecastsheet.portfolioid}, processing rows")
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
                        pflr.portfolioid = pfforecastsheet.portfolioid
                        pflr.yearmonth = datetime.date(pfforecastsheet.year, month, 1)
                        pflr.laborroleid = row[0]
                        pflr.forecastedhours = re.sub(r'[^0-9.]', '', row[monthcol])
                        pflr.forecasteddollars = re.sub(r'[^0-9.]', '', row[monthcol+2])
                        pflr.source = source
                        pflr.updateddate = datetime.date.today()
                        db.session.add(pflr)
                        loglines.append(f"  {pflr.laborroleid} {pflr.forecastedhours} hours at ${pflr.forecasteddollars} in {pflr.yearmonth}")
                        if index % 100 == 0:
                            db.session.commit()

        db.session.commit()
        await asyncio.sleep(1)

    return loglines

# AutoML using MLJAR
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
    startdate = today.replace(day=1, month=1) # TODO:remove - relativedelta(years=1)
    lookaheadmonths = 14

    laborroles = db.session.query(LaborRole).all()

    # load up the CI data for each portfolio+month combination
    pfinfodict = {}

    pfinforows = bigquery.Client().query(automl_query).result()
    for row in pfinforows:
        pfinfodict[f"{row['AccountPortfolioID']}-{row['YearMonth']}"] = row

    commitrowcount = 0
    loglines.append(f"processing {startdate}")

    # for each portfolio with forecasts from start month to lookaheadmonths from now
    for pf in db.session.query(PortfolioForecast).filter(
        PortfolioForecast.yearmonth >= startdate,
        PortfolioForecast.yearmonth <= startdate + relativedelta(months=lookaheadmonths)
    ).order_by(PortfolioForecast.yearmonth).all():
        loglines.append(f"  for portfolio {pf.portfolioid}, processing {pf.yearmonth}")
        starttime = datetime.datetime.now()
        pfinfo = None
        pfinfokey = f"{pf.portfolioid}-{pf.yearmonth.year*100 + pf.yearmonth.month}"
        if pfinfokey in pfinfodict:
            pfinfo = pfinfodict[pfinfokey]
        else:
            # probably this is a future month; assume it's the same as the current month
            loglines.append(f"    no CI data for {pfinfokey}; trying last month's data")
            lastmonth = today - relativedelta(months=1)
            pfinfokey = f"{pf.portfolioid}-{lastmonth.year*100 + lastmonth.month}"
            if pfinfokey in pfinfodict:
                pfinfo = pfinfodict[pfinfokey]
            else:
                # no CI data for this month either; just use blank data
                loglines.append(f"    AND no CI data for {pfinfokey}! going with blank data")
                pfinfo = {
                    "YearMonth": pf.yearmonth.year*100 + pf.yearmonth.month,
                    "PDName": None,
                    "GADName": None,
                    "CSTName": None,
                    "OfficeName": None,
                    "CIChannel": "",
                    "CILifecycle": "",
                    "CIDeliverable": "",
                }

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
                'YearMonth': pfinfo["YearMonth"],
                'PDName': pfinfo["PDName"] or pf.portfolio.currpdname,
                'GADName': pfinfo["GADName"] or pf.portfolio.currgadname,
                'AccountPortfolioID': pf.portfolio.id,
                'ClientName': pf.portfolio.clientname,
                'PortfolioName': pf.portfolio.name,
                'LaborRole': lr.id,
                'CSTName': pfinfo["CSTName"] or pf.portfolio.currbusinessunit,
                'OfficeName': pfinfo["OfficeName"] or pf.portfolio.currofficename,
                'CIChannel': pfinfo["CIChannel"],
                'CILifecycle': pfinfo["CILifecycle"],
                'CIDeliverable': pfinfo["CIDeliverable"],
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
                })
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
    loglines.append(f"  running query")
    rows = bigquery.Client().query(automl_query).result()
    loglines.append(f"  results rows {rows.total_rows}")
    df = rows.to_dataframe()
    df.to_csv(bq_csv_path)

    # split into train and test, keeping the most recent 3 months for test
    loglines.append(f"  splitting into train and test")
    # split date point is yearmonth in int format
    splitdate = int((datetime.date.today() - relativedelta(months=3)).strftime("%Y%m"))
    X_train = df[df.YearMonth < splitdate].drop("Hours", axis=1)
    X_test = df[df.YearMonth >= splitdate].drop("Hours", axis=1)
    y_train = df[df.YearMonth < splitdate]["Hours"]
    y_test = df[df.YearMonth >= splitdate]["Hours"]
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

