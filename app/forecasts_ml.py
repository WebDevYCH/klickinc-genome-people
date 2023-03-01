#!/usr/bin/env python3

# Intel-specific optimizations
try:
    from sklearnex import patch_sklearn 
    patch_sklearn()
except:
    pass

from collections import OrderedDict
from re import A
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import SGDClassifier
from sklearn import svm
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import GridSearchCV
import xgboost as xgb
import lightgbm as lgb

import sys
import numpy as np
import matplotlib.pyplot as plt
import talib as ta
from IPython.display import display
import pandas as pd
import seaborn as sns 

from google.cloud import bigquery
from core import *

pd.options.mode.chained_assignment = None  # default='warn'

if len(sys.argv) < 3:
    print("Usage: " + sys.argv[0] + " [jobfunction] [clientname=xx or employeecst=xx] [opt args]")
    print("  opt arguments:")
    print("    hyperoptonly=true|false")
    print("    predictonly=true|false")
    print("    doplot=true|false")
    print("    data_years=10")
    print("    lookback_years=1")
    print("    technique=lgb|xgboost|forest")
    print("    wfosteps=4")
    print("    estimators=250")
    print("    maxdepth=10")
    print("    learning_rate=0.3")
    print("    min_child_weight=1")
    print("    colsample_bytree=0.8")
    print("    reg_alpha=0.1")
    print("    reg_lambda=0.1")
    print()

    print()
    quit()

jobfunction = sys.argv[1]

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
clientname = getarg("clientname", None)
employeecst = getarg("employeecst", None)
hyperoptonly = getarg("hyperoptonly", False)
predictonly = getarg("predictonly", False)
doplot = getarg("doplot", True)

data_years = getarg("data_years", 10)
lookback_years = getarg("lookback_years", 1)
lookforward_days = getarg("lookforward_days", 120)
technique = getarg("technique", 'lgb')
wfosteps = getarg("wfosteps", 4)

# hyperparameters
estimators = getarg("estimators", 250)
maxdepth = getarg("maxdepth", 10)
learning_rate = getarg("learning_rate", 0.3)
min_child_weight = getarg("min_child_weight", 1)
colsample_bytree = getarg("colsample_bytree", 0.8)
reg_alpha = getarg("reg_alpha", 0.1)
reg_lambda = getarg("reg_lambda", 0.1)

# LOAD DATA

print("Loading data...")
start_year = datetime.date.today().year - data_years

# bigquery sql (load up for each combination of job function and division)
clientcstclause = ""
if clientname is not None:
    clientcstclause = f"and p.ClientName like '%{clientname}%' "
if employeecst is not None:
    clientcstclause = f"and fact.EmployeeBusinessUnit like '%{employeecst}%' "

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
and jf.Name like '%{jobfunction}%' 
{clientcstclause}
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
display(df)

# take out weekends
df = df[df.index.dayofweek < 5]

display(df)

# ADD FEATURES
print("Adding features...")

def zscore(src, timeperiod):
    avg = ta.SMA(src, timeperiod = timeperiod)
    std = ta.STDDEV(src, timeperiod = timeperiod)
    zscore = (src - avg)/std
    return zscore

df['rsi_2']     = ta.RSI(df['Hours'], timeperiod = 2)
df['rsi_3']     = ta.RSI(df['Hours'], timeperiod = 3)
df['rsi_5']     = ta.RSI(df['Hours'], timeperiod = 5)
#df['rsi_8']     = ta.RSI(df['Hours'], timeperiod = 8)
df['rsi_14']    = ta.RSI(df['Hours'], timeperiod = 14)
df['rsi_20']    = ta.RSI(df['Hours'], timeperiod = 20)

df['zscore_4']  = zscore(df['Hours'], timeperiod = 4)
df['zscore_8']  = zscore(df['Hours'], timeperiod = 8)
df['zscore_17'] = zscore(df['Hours'], timeperiod = 17)
#df['zscore_20'] = zscore(df['Hours'], timeperiod = 20)

df['sma_10']   = ta.SMA(df['Hours'], timeperiod = 100)
df['sma_20']   = ta.SMA(df['Hours'], timeperiod = 100)
#df['sma_50']   = ta.SMA(df['Hours'], timeperiod = 100)
df['sma_100']   = ta.SMA(df['Hours'], timeperiod = 100)
df['sma_150']   = ta.SMA(df['Hours'], timeperiod = 150)
df['sma_200']   = ta.SMA(df['Hours'], timeperiod = 200)
df['ema_200']   = ta.EMA(df['Hours'], timeperiod = 200)

#df['dayofweek'] = df.index.dayofweek
df['month']     = df.index.month
df['dayofmonth']= df.index.day

display(df)

print("TRAINING MODEL")

def make_model():
    # Select a model to fit and test
    if technique == 'forest':
        model = RandomForestRegressor(n_estimators=estimators, max_depth=maxdepth, min_samples_split=50, n_jobs=-1, random_state=42)
    elif technique == 'xgboost':
        model = xgb.XGBRegressor(n_estimators=estimators, max_depth=maxdepth, learning_rate=learning_rate, colsample_bytree=colsample_bytree, 
                                    min_child_weight=50, n_jobs=-1, random_state=42)
    elif technique == 'lgb':
        params = {
            'objective': 'regression',
            'n_estimators': estimators,
            'max_depth': maxdepth,
            'learning_rate': learning_rate,
            'colsample_bytree': colsample_bytree,
            'min_child_weight': 50,
            'n_jobs': -1,
            'random_state': 42,
            #'linear_tree': True,
        }
        model = lgb.LGBMRegressor(**params)
    else:
        print(f"ERROR: Unknown technique: {technique}")
        exit()
    return model

# set up NextHours, representing the next day's hours
df['NextHours'] = df['Hours'].shift(-1)

# set up prediction target variable NextHours, representing the next 20 days' hours summed up
#df['NextHours'] = df['Hours'].rolling(window=20, min_periods=1).sum().shift(-20)


# replace infinte values with NaNs and drop any rows with NaN (but keep the last line for prediction)
lastline = df.tail(1)
df = df[:-1]
df.replace([np.inf, -np.inf], np.nan, inplace = True)
df.dropna(inplace = True)
df = pd.concat([df, lastline])

# predictors are all columns except the one called 'NextHours'
predictors = df.columns.tolist()
predictors.remove('NextHours')
print("predictors = ", predictors)

#df.to_csv('logs/testfullinputs.csv', date_format='%Y-%m-%d') 

# train is everything in df before X year ago, based on the date column
pivot_date = datetime.date.today() - datetime.timedelta(days = int(365*lookback_years))
length = len(df)
train = df.loc[: pivot_date]
# test is from pivot_date to all but the last record of df
test = df.loc[pivot_date :].drop(df.tail(1).index)
# if the last train record and first test record overlap, drop the train record
if train.index[-1] == test.index[0]:
    train = train.drop(train.tail(1).index)

# pre-fill predict dataframe with the next 120 days, and the structure of the test dataframe
predict = pd.DataFrame(index=pd.date_range(start=datetime.date.today(), periods=120, freq='D'), columns=test.columns)
# then insert the last record of df into the first row of predict
predict = pd.concat([df.tail(1), predict])
# then fill in predictor columns where possible
predict['dayofweek'] = predict.index.dayofweek
predict['month']     = predict.index.month
predict['dayofmonth'] = predict.index.day
# remove weekends
predict = predict[predict['dayofweek'] < 5]

if hyperoptonly:
    print(f"Hyperparameter optimization only; len(train)={len(train)}, len(test)={len(test)}")
    model = make_model()
    param_grid = {}
    if technique == 'forest':
        param_grid['n_estimators'] = [250, 500, 1000, 2000, 4000, 5000],
        param_grid['max_depth'] = [2, 3, 4, 5, 10, 20, 40],
        param_grid['min_samples_split'] = [2, 5, 10, 20, 50, 100]
    elif technique == 'xgboost':
        param_grid['n_estimators'] = [250, 500, 1000, 2000, 4000, 5000],
        param_grid['max_depth'] = [2, 3, 4, 5, 10, 20, 40],
        param_grid['learning_rate'] =  [0.01, 0.05, 0.1, 0.2, 0.5, 1.0]
        param_grid['min_child_weight'] = [1, 5, 10, 20, 50, 100]
        param_grid['lambda'] = [0, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
        param_grid['alpha'] = [0, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
        param_grid['colsample_bytree'] = [0.1, 0.2, 0.5, 0.7, 1.0]
    elif technique == 'sgd':
        param_grid['loss'] = ['modified_huber', 'hinge', 'perceptron', 'squared_hinge', 'log_loss', 'squared_epsilon_insensitive', 'epsilon_insensitive', 'squared_error', 'huber']
        param_grid['penalty'] = ['l2', 'l1', 'elasticnet']
        param_grid['alpha'] = [0.0001, 0.001, 0.01, 0.1, 1.0]
        param_grid['max_iter'] = [100, 1000, 10000]
        param_grid['tol'] = [0.0001, 0.001, 0.01, 0.1, 1.0]
    grid_search = GridSearchCV(model, param_grid, n_jobs=-1, verbose=1)
    grid_search.fit(df.head(-1)[predictors], df.head(-1)["NextHours"])
    print(f"Best parameters: {grid_search.best_params_}")
    #print(f"Best estimator: {grid_search.best_estimator_}")
    exit()


if not predictonly:
    # train/test loops based on splitting the test set into wfosteps chunks
    wfolength = int(len(test) / wfosteps)
    print(f"Training+predicting WFO with {wfosteps} steps of {wfolength} data points each (last step may be shorter); len(training)={len(train)}, len(test)={len(test)}")
    train["NextHoursPredicted"] = np.nan
    test["NextHoursPredicted"] = np.nan
    for wfostep in range(0, wfosteps):

        trainstartpos = wfostep * wfolength
        trainendpos = (wfostep * wfolength) - 1 # how much of the main test set to use for training
        teststartpos = trainstartpos
        testendpos = min(teststartpos + wfolength, len(test))
        if wfostep == wfosteps - 1:
            testendpos = len(test) # sometimes rounding errors mean we wouldn't normally predict the last record or two
        model = make_model()

        if trainendpos != -1:
            print(f"Training+predicting WFO round {wfostep+1}/{wfosteps} thistrain=train[{trainstartpos}:]+test[:{trainendpos}] thistest=test[{teststartpos}:{testendpos}]")
            thistrain = pd.concat([train[trainstartpos:], test[:trainendpos]])
        else:
            print(f"Training+predicting WFO round {wfostep+1}/{wfosteps} thistrain=train[{trainstartpos}:] thistest=test[{teststartpos}:{testendpos}]")
            thistrain = train[trainstartpos:]
        thistest = test[teststartpos:testendpos]

        model.fit(thistrain[predictors], thistrain["NextHours"])

        # predict the training subset
        thistrain['NextHoursPredicted'] = model.predict(thistrain[predictors])
        train.update(thistrain[['NextHoursPredicted']])

        # predict the test subset
        thistest['NextHoursPredicted'] = model.predict(thistest[predictors])
        test.update(thistest[['NextHoursPredicted']])

# predict the next 120 days
model = make_model()
trainstartpos = len(test)
thistrain = pd.concat([train[trainstartpos:], test])
print(f"Training on train+test set for extrapolation")
# train the model on the subset
model.fit(thistrain[predictors], thistrain["NextHours"])
# now predict
print(f"Predicting extrapolation for {lookforward_days} days")
predict['NextHoursPredicted'] = model.predict(predict[predictors])

if predictonly:
    exit()

print("RESULTS SUMMARY")

train_r2_error = r2_score(train['NextHours'], train['NextHoursPredicted'])
print(f"prediction accuracy in training data: {train_r2_error}")
test_r2_error = r2_score(test['NextHours'], test['NextHoursPredicted'])
print(f"prediction accuracy in test data: {test_r2_error}")

print()

print("SPECIFIC PREDICTIONS FOR TEST SET")
testpredict = pd.concat([test, predict])

display(test)
print()

# descriptive statistics
stats = OrderedDict()

thisyear = datetime.date.today().year

stats['** PARAMETERS'] = '--'
stats['jobfunction'] = jobfunction
stats['clientname'] = clientname
stats['employeecst'] = employeecst
stats['data_years'] = data_years
stats['technique'] = technique
stats['estimators'] = estimators
stats['maxdepth'] = maxdepth
stats['learning_rate'] = learning_rate
stats['colsample_bytree'] = colsample_bytree
stats['wfosteps'] = wfosteps

stats['** RESULTS'] = '--'
stats['train_r2_error'] = train_r2_error
stats['test_r2_error'] = test_r2_error
stats['test_bars'] = len(test)
stats['train_bars'] = len(train)

summary = "SUMMARY: "
for key, value in stats.items():
    summary += f"{key}={value}, "
print(summary)
print()

print("SUMMARY TABLE")
summarytable = pd.DataFrame.from_dict(stats, orient='index', columns=['value'])
display(summarytable)

# write pandas dataframe test to an excel file
#test.to_csv('logs/testprediction.csv', date_format='%Y-%m-%d') 

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


if doplot:
    # setting plotting parameters

    #plt.style.use('fivethirtyeight')
    #plt.rcParams.update({'font.size': 13})
    fig, ax = plt.subplots(figsize=(10, 10))

    # add legend, with first datapoint NextHours and second NextHoursPredicted

    plt.subplot(3, 1, 1, title='Predicted vs Actual')
    plt.plot(test['NextHours'], label='hours')
    plt.plot(testpredict['NextHoursPredicted'], label='hours extrapolated')
    plt.plot(test['NextHoursPredicted'], label='hours predicted')
    plt.legend()

    plt.subplot(3, 1, 2, title='Predicted vs Actual Cumulative')
    plt.plot(test['NextHours'].cumsum(), label='hours')
    plt.plot(testpredict['NextHoursPredicted'].cumsum(), label='hours extrapolated')
    plt.plot(test['NextHoursPredicted'].cumsum(), label='hours predicted')
    plt.text(0.98, 0.5, summarytable.to_string(), horizontalalignment='right', verticalalignment='center', transform=plt.gca().transAxes, fontsize=8, color='red')
    plt.legend()

    plt.subplot(3, 1, 3, title='Feature Importance')
    plot_feature_importance(model.feature_importances_,predictors,technique)

    plt.show()
