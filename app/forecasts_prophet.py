#!/usr/bin/env python3

from collections import OrderedDict
from sklearn.metrics import r2_score
from fbprophet import Prophet
from fbprophet.plot import plot_plotly, plot_components_plotly
import orbit
from orbit.utils.dataset import load_iclaims
from orbit.models import ETS
from orbit.diagnostics.plot import plot_predicted_data

import sys
import numpy as np
import matplotlib.pyplot as plt
from IPython.display import display
import pandas as pd
import seaborn as sns 

from google.cloud import bigquery
from core import *

pd.options.mode.chained_assignment = None  # default='warn'
import warnings
warnings.filterwarnings("ignore", message="The frame.append method is deprecated")


if len(sys.argv) > 1 and sys.argv[1] in ['help', '-h', '--h', '--help']:
    print("Usage: " + sys.argv[0] + " [opt args]")
    print("  opt arguments:")
    print("    jobfunction=xx")
    print("    clientname=xx")
    print("    employeecst=xx")
    print("    metric=Hours|ExternalValueDollars")
    print("    technique=prophet|orbit")
    print("    hyperoptonly=true|false")
    print("    predictonly=true|false")
    print("    doplot=true|false")
    print("    data_years=10")
    print("    lookback_years=1")

    print()
    quit()

# pick up args of the format arg=value
def getarg(argname, default):
    for arg in sys.argv:
        if arg.startswith(argname + '='):
            if type(default) is int:
                return int(arg.split('=')[1])
            elif type(default) is float:
                return float(arg.split('=')[1])
            elif type(default) is bool:
                return arg.split('=')[1].lower() == 'true' or arg.split('=')[1].lower() == '1' or arg.split('=')[1].lower() == 'yes'
            else:
                return arg.split('=')[1].replace("'", "")
    return default


# parameters
jobfunction = getarg("jobfunction", None)
clientname = getarg("clientname", None)
employeecst = getarg("employeecst", None)
predictonly = getarg("predictonly", False)
doplot = getarg("doplot", True)
technique = getarg("technique", "prophet")
data_years = getarg("data_years", 8)
report_days = getarg("report_days", 1200)
forecast_days = getarg("forecast_days", 365)
wfosteps = getarg("wfosteps", 6)
wfodaysperstep = getarg("wfodaysperstep", 90)

# LOAD DATA

print("Loading data...")
start_year = datetime.date.today().year - data_years

# bigquery sql (load up for each combination of job function and division)
whereclause = ""
if jobfunction is not None:
    whereclause += f"and jf.Name like '%{jobfunction}%' "
if clientname is not None:
    whereclause = f"and p.ClientName like '%{clientname}%' "
if employeecst is not None:
    whereclause = f"and fact.EmployeeBusinessUnit like '%{employeecst}%' "

query = f"""
select 
d.ActualDate as Date,
sum(Hours) as Hours
from `genome-datalake-prod.GenomeDW.F_Actuals` fact
join `genome-datalake-prod.GenomeDW.Portfolio` p on fact.Portfolio=p.Portfolio
join `genome-datalake-prod.GenomeDW.DateDimension` d on fact.Date=d.DateDimension
join `genome-datalake-prod.GenomeDW.Project` pr on fact.Project=pr.Project
join `genome-datalake-prod.GenomeDW.LaborRole` lr on fact.LaborRole=lr.LaborRole
join `genome-datalake-prod.GenomeDW.JobFunction` jf on fact.JobFunction=jf.JobFunction
where pr.Billable=true
and d.ActualDate >= '{start_year}-01-01'
{whereclause}
group by 
d.ActualDate
"""

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "../keys/google-key.json"
bqresult = bigquery.Client().query(query)
# convert to dataframe with date as index
df = bqresult.to_dataframe()
df['Date'] = pd.to_datetime(df['Date'])
df = df.set_index('Date')
df = df.sort_index()

# rename Date to DS and Hours to Y
df['ds'] = df.index
df['y'] = df['Hours']
df['yhat'] = np.nan
df['yhat_lower'] = np.nan
df['yhat_upper'] = np.nan
display(df)
print()

def create_model():
    if technique == 'prophet':
        model = Prophet()
        model.add_country_holidays(country_name='CA')
    elif technique == 'orbit':
        model = ETS(
            response_col='y',
            date_col='ds',
            seasonality=7,
            seed=42,
        )
    return model

# walk forward optimization (really evaluation)
print("Walk forward optimization...")
for wfostep in range(0, wfosteps):
    pivot = len(df) - (wfodaysperstep*(wfosteps-wfostep))
    print(f"  step {wfostep}... training on df[:{pivot}] and testing on df[{pivot+1}:{pivot+wfodaysperstep}]]")
    # split into train and test
    train = df[:pivot][['ds','y']]
    test = df[pivot+1:pivot+wfodaysperstep][['ds','y']]
    # train model
    model = create_model()
    model.fit(train)
    # predict
    #forecast = model.predict(model.make_future_dataframe(periods=forecast_days))
    forecast = model.predict(test)
    # set index to ds
    forecast = forecast.set_index('ds')
    # save back to df
    df.update(forecast[['yhat','yhat_lower','yhat_upper']])

df.to_csv(f"../logs/prophet-wfo.csv")

r2df = df[['y','yhat']]
# clear NaN and Inf values
r2df.replace([np.inf, -np.inf], np.nan, inplace = True)
r2df.dropna(inplace = True)
# calculate r2
r2_error = r2_score(r2df['y'], r2df['yhat'])
print(f"prediction accuracy in WFO: {r2_error}")

print("Training full model...")
model = create_model()
model.fit(df)


print("Predicting...")
forecast = model.predict(model.make_future_dataframe(periods=forecast_days))
# make ds the index, but also a column
forecast = forecast.set_index('ds')
forecast['ds'] = forecast.index
display(forecast)

#forecast.to_csv(f"../logs/prophet-forecast.csv")

# descriptive statistics
stats = OrderedDict()

thisyear = datetime.date.today().year

stats['** PARAMETERS'] = '--'
stats['jobfunction'] = jobfunction
stats['clientname'] = clientname
stats['employeecst'] = employeecst
stats['data_years'] = data_years
stats['report_days'] = report_days
stats['forecast_days'] = forecast_days
stats['wfosteps'] = wfosteps
stats['wfodaysperstep'] = wfodaysperstep

stats['** RESULTS'] = '--'
stats['r2_error'] = r2_error

summary = "SUMMARY: "
for key, value in stats.items():
    summary += f"{key}={value}, "
print(summary)
print()

print("SUMMARY TABLE")
summarytable = pd.DataFrame.from_dict(stats, orient='index', columns=['value'])
display(summarytable)

def plot_feature_importance(importance,names,model_type):

    #Create arrays from feature importance and feature names
    feature_importance = np.array(importance)
    feature_names = np.array(names)

    #print(f"feature_importance={feature_importance} (len {len(feature_importance)})")
    #print(f"feature_names={feature_names} (len {len(feature_names)})")

    #Create a DataFrame using a Dictionary
    data={'feature_names':feature_names,'feature_importance':feature_importance}
    fi_df = pd.DataFrame(data)

    #Sort the DataFrame in order decreasing feature importance
    fi_df.sort_values(by=['feature_importance'], ascending=False,inplace=True)

    #Plot Searborn bar chart
    sns.barplot(x=fi_df['feature_importance'], y=fi_df['feature_names'])
    #Add chart labels
    plt.title(model_type + 'Feature Importance')
    plt.xlabel('Feature Importance')
    plt.ylabel('Feature Name')


# PLOT
if doplot:
    print("Plotting...")
    #fig = model.plot(forecast)
    #plt.show()
    #fig = model.plot_components(forecast)
    #plt.show()

    # setting plotting parameters

    #plt.style.use('fivethirtyeight')
    #plt.rcParams.update({'font.size': 13})
    fig, ax = plt.subplots(figsize=(10, 10))

    # add legend, with first datapoint NextHours and second NextHoursPredicted

    plt.subplot(2, 1, 1, title='Predicted+Forecasts vs Actual')
    plt.plot(df['y'].tail(report_days), '.', label='hours')
    plt.plot(df['yhat'].tail(report_days), '.', label='hours predicted WFO OOS')
    plt.plot(forecast['yhat'].tail(report_days+forecast_days), '.', label='hours forecasted')
    plt.legend()

    plt.subplot(2, 1, 2, title='Predicted+Forecasts vs Actual Cumulative')
    plt.plot(df.tail(report_days)['y'].cumsum(), label='hours')
    #plt.plot(df.tail(report_days)['yhat'].cumsum(), label='hours predicted WFO OOS')
    plt.plot(forecast['yhat'].tail(report_days+forecast_days).cumsum(), label='hours forecasted', color='green')
    plt.text(0.98, 0.5, summarytable.to_string(), horizontalalignment='right', verticalalignment='center', transform=plt.gca().transAxes, fontsize=8, color='red')
    plt.legend()

    #plot_feature_importance(model.feature_importances_,predictors,'prophet')
    #plt.subplot(3, 1, 3, title='Forecast')
    #plot_plotly(model, forecast)

    plt.show()

