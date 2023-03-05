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

###################################################################
## LABOR FORECASTS CHARTING URLs

# GET /p/forecasts/charts
@app.route('/p/forecasts/charts')
@login_required
def forecast_charts():
    thisyear = datetime.date.today().year
    # if it's after October, show the next year's forecasts
    if datetime.date.today().month > 10:
        thisyear += 1

    startyear = thisyear-2
    endyear = thisyear+1
    return render_template('forecasts/charts.html', 
        title='Forecast Charts', 
        startyear=startyear, endyear=endyear, thisyear=thisyear)
