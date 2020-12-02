from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier,GradientBoostingClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
import pandas as pd
import openpyxl
from sklearn.metrics import confusion_matrix
from numpy import sqrt
import matplotlib.pyplot as plt
from yahoofinancials import YahooFinancials
import os
import datetime
from pathlib import Path


def df_scaler(df):
	for col in df:
		df[col] = (df[col] - df[col].mean())/df[col].std()
	return df	

p = Path(os.path.abspath(__file__)).parents[1]
filename = os.path.join(p, 'Ongoing predictions','combined_training_data2.xlsx')
dfs = pd.read_excel(filename,sheet_name=None)
keys = list(dfs.keys())



for key,df in dfs.items():

	classifiers = df['Classification']
	X_train, X_test,y_train,y_test = train_test_split(df.drop(['date','5d Avg Beta Adj Return','Next Day Return','Classification'],axis=1),classifiers,test_size=0.2, shuffle=False)
	X_train = df_scaler(X_train)
	X_test = df_scaler(X_test)
	model =RandomForestClassifier()
	model.fit(X_train,y_train)
	y_pred = model.predict(X_test)



	if key==keys[0]:
		df_returns =  df[['date','Next Day Return']].iloc[df.shape[0] - X_test.shape[0]:]
		df_returns.rename({'Beta Adj Return' : key},axis=1,inplace=True)
		df_ypred = df[['date','Beta Adj Return']].iloc[df.shape[0] - X_test.shape[0]:]
	else:
		df_returns[key] =  df['Next Day Return'].iloc[df.shape[0] - X_test.shape[0]:]
	df_ypred[key] = y_pred.tolist()
	
df_returns.reset_index(drop=True,inplace=True)
df_ypred.drop('Beta Adj Return',axis=1, inplace=True)
df_predictions = df_ypred.copy()
df_ypred.reset_index(drop=True,inplace=True)

df_positions = df_ypred.copy()
df_positions.drop('date',axis=1,inplace =True)

df_positions1=df_positions.abs()

cols=df_positions.columns.values
df_positions[cols] = df_positions[cols].div(df_positions1[cols].sum(axis=1), axis=0)
df_returns.drop('date',axis=1,inplace =True)

df_daily_perf = (df_returns*df_positions).sum(axis=1)



df_cumulative_perf = df_daily_perf.copy()
df_daily_perf +=1
for i in range(0,df_daily_perf.shape[0]):
	df_cumulative_perf.iloc[i] = df_daily_perf.iloc[:i+1].product()

df_cumulative_perf.iloc[0]=1
df_plot = df_ypred.iloc[:,0:1].copy()
df_plot['strategy'] = df_cumulative_perf.copy()

date_start = str(df_plot['date'].iloc[0])
date_end = str(datetime.datetime.strptime(df_plot['date'].iloc[-1], '%Y-%m-%d').date() + datetime.timedelta(days=1))

#getting S&P500 data

asset='^GSPC'
yahoo_financials = YahooFinancials(asset)

data = yahoo_financials.get_historical_price_data(start_date=date_start, 
                                              end_date=date_end, 
                                              time_interval='daily')


df_sp500 = pd.DataFrame({asset: {x['formatted_date']: x['adjclose'] for x in data[asset]['prices']}})
df_sp500.index.name='date'
df_sp500.reset_index(inplace=True)
df_sp500['SP500']= df_sp500['^GSPC'].copy()
df_sp500['SP500'].iloc[0]=1

for i in range(1,df_sp500.shape[0]):
	df_sp500['SP500'].iloc[i] = 1 + (df_sp500['^GSPC'].iloc[i] - df_sp500['^GSPC'].iloc[0])/df_sp500['^GSPC'].iloc[0]

df_sp500.drop('^GSPC',axis=1, inplace=True)


df_plot = df_plot.merge(df_sp500,how='inner',on='date')

p = Path(os.path.abspath(__file__)).parents[1]
filename = os.path.join(p, 'Ongoing predictions','historical_data1.xlsx.xlsx')
writer = pd.ExcelWriter(filename, engine='openpyxl') 
df_plot.to_excel(writer, sheet_name='historical performance',index=False)
df_predictions.to_excel(writer, sheet_name='predictions',index=False)
writer.save()


df_plot.plot(x ='date', y=['strategy','SP500'], kind = 'line')
plt.show()
