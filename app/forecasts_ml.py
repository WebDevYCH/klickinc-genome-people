#!/usr/bin/env python3

# Intel-specific optimizations
try:
    from sklearnex import patch_sklearn 
    patch_sklearn()
except:
    pass

from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import SGDClassifier
from sklearn import svm
from sklearn.model_selection import GridSearchCV
import xgboost as xgb

import sys
import numpy as np
import matplotlib.pyplot as plt
import talib as ta
from IPython.display import display
import pandas as pd

pd.options.mode.chained_assignment = None  # default='warn'

if len(sys.argv) < 2:
    print("Usage: " + sys.argv[0] + "")
    print()
    quit()

plt.close('all')

from core import *


# query parameters
laborcat = None
laborrole = None
jobfunction = None

# parameters
data_years = 7
lookback_years = 1
technique = 'xgboost'
wfosteps = 4

# hyperparameters
n_estimators = 100
max_depth = 10
learning_rate = 0.1
min_child_weight = 1
gamma = 0.1
subsample = 0.8
colsample_bytree = 0.8
reg_alpha = 0.1
reg_lambda = 0.1
