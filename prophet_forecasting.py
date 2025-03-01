import numpy as np
import pandas as pd
from pandas.api.types import CategoricalDtype
import seaborn as sns
import matplotlib.pyplot as plt
from prophet import Prophet
from sklearn.metrics import mean_squared_error, mean_absolute_error
import warnings
warnings.filterwarnings("ignore")
import process_data

plt.style.use('ggplot')
plt.style.use('fivethirtyeight')

def mean_absolute_percentage_error(y_true, y_pred):
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    return np.mean(np.absolute((y_true - y_pred)/y_true)) * 100

data_raw = process_data.get_data()
#print(data_raw.head())

#-------------------------#plot imported data---------------------------------------------------------------
# color_pal = sns.color_palette()
# data_raw.plot(
#     style='.',
#     figsize=(10, 5),
#     ms=1,
#     color=color_pal[0],
#     title='Raw input data: wh over date times'

# )
# plt.show()
#----------------------------------------------------------------------------------------

#---------------------------#Time series features.-------------------------------------------------------------

cat_type = CategoricalDtype(categories=['Monday','Tuesday', 'Wednesday','Thursday','Friday','Saturday','Sunday'],ordered=True)

def create_features(df, label=None):
    """
    Creates time series features from datetime index.
    """
    df = df.copy()
    df['date'] = df.index
    df['hour'] = df['date'].dt.hour
    df['dayofweek'] = df['date'].dt.dayofweek
    df['weekday'] = df['date'].dt.day_name()
    df['weekday'] = df['weekday'].astype(cat_type)
    df['quarter'] = df['date'].dt.quarter
    df['month'] = df['date'].dt.month
    df['year'] = df['date'].dt.year
    df['dayofyear'] = df['date'].dt.dayofyear
    df['dayofmonth'] = df['date'].dt.day
    df['weekofyear'] = df['date'].dt.isocalendar().week
    df['date_offset'] = (df.date.dt.month*100 + df.date.dt.day - 320)%1300

    df['season'] = pd.cut(df['date_offset'], [0, 300, 602, 900, 1300], 
                          labels=['Spring', 'Summer', 'Fall', 'Winter']
                   )
    X = df[['hour','dayofweek','quarter','month','year',
           'dayofyear','dayofmonth','weekofyear','weekday',
           'season']]
    if label:
        y = df[label]
        return X, y
    return X

X, y = create_features(data_raw, label='Energy_Wh')
features_and_target = pd.concat([X, y], axis=1)
print(features_and_target.head())

#Plot showing trend on day of week and seasonality
# fig, ax = plt.subplots(figsize=(10, 5))
# sns.boxplot(data=features_and_target.dropna(),
#             x='weekday',
#             y='Energy_Wh',
#             hue='season',
#             ax=ax,
#             linewidth=1)
# ax.set_title('Charging energy by day of week')
# ax.set_xlabel('Day of Week')
# ax.set_ylabel('Energy (Wh)')
# ax.legend(bbox_to_anchor=(1, 1))
# plt.show()

#Plot showing hour of day box with seasonality
# fig, ax = plt.subplots(figsize=(10, 5))
# sns.boxplot(data=features_and_target.dropna(),
#             x='hour',
#             y='Energy_Wh',
#             hue='season',
#             ax=ax,
#             linewidth=1)
# ax.set_title('Charging energy by hour of day')
# ax.set_xlabel('Hour of day')
# ax.set_ylabel('Energy (Wh)')
# ax.legend(bbox_to_anchor=(1, 1))
# plt.show()
#----------------------------------------------------------------------------------------

#-----------------------------Train / Test split-----------------------------------------------------------

split_date = '1-aug-2024'
data_train = data_raw.loc[data_raw.index <= split_date].copy()
data_test = data_raw.loc[data_raw.index > split_date].copy()

# Plot train and test so you can see where we have split
# data_test \
#     .rename(columns={'Energy_Wh': 'TEST SET'}) \
#     .join(data_train.rename(columns={'Energy_Wh': 'TRAINING SET'}),
#           how='outer') \
#     .plot(figsize=(10, 5), title='test', style='.', ms=1)
# plt.show()

#----------------------------------------------------------------------------------------

#----------------------------Prophet Implementation------------------------------------------------------------

data_train_prophet = data_train.reset_index().rename(columns={'Start time':'ds','Energy_Wh':'y'})

model = Prophet()
model.fit(data_train_prophet)

#test data frame
data_test_prophet = data_test.reset_index().rename(columns={'Start time':'ds','Energy_Wh':'y'})

test_predict = model.predict(data_test_prophet)

print(test_predict.head())