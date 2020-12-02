import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from yahoofinancials import YahooFinancials
import datetime
import numpy as np
import stock_tweet_analysis_repo as star
import os
pd.options.mode.chained_assignment = None  # disable chain assignment warning

def linear_regression(x,y):
	model = LinearRegression().fit(x, y)
	return model.coef_.item()

def calc_classification(ret,stdev1):
	z= float(ret)/stdev1
	if abs(z)<0.5:
		return 0
	if z>=0.5 and z<1:
		return 1
	if z<=-0.5 and z>-1:
		return -1
	if z>=1:
		return 2
	if z<=-1:
		return -2
	


def import_stock_prices(d0,d1):
	#getting the list of all S&P500 constituents
	assets = star.get_cashtags()
	assets.insert(0,'^GSPC')

	# getting data from d0 - 6 months as need to calculate 6 month rolling stock beta to SP500
	date_start = str(d0 - datetime.timedelta(days=180))
	date_end = str(d1)

	yahoo_financials = YahooFinancials(assets)

	data = yahoo_financials.get_historical_price_data(start_date=date_start, 
	                                              end_date=date_end, 
	                                              time_interval='daily')

	a0=assets[0]

	calc_beta_df = pd.DataFrame({a0: {x['formatted_date']: (x['adjclose'] - x['open'])/x['open'] for x in data[a0]['prices']}})
	calc_beta_df.index.name='date'
	assets.remove('^GSPC')

	volumes_df = pd.DataFrame({a0: {x['formatted_date']: x['volume'] for x in data[a0]['prices']}})
	volumes_df.index.name='date'

	for a in assets:
		try:
			calc_beta_df1 = pd.DataFrame({a: {x['formatted_date']: (x['close'] - x['open'])/x['open'] for x in data[a]['prices']}})
			calc_beta_df1.index.name='date'
			calc_beta_df = pd.merge(calc_beta_df,calc_beta_df1,on='date',how='outer')

			volumes_df1 = pd.DataFrame({a: {x['formatted_date']: x['volume'] for x in data[a]['prices']}})
			volumes_df1.index.name='date'
			volumes_df = pd.merge(volumes_df,volumes_df1,on='date',how='outer')

		except KeyError:
			pass

	calc_beta_df.reset_index(inplace=True)
	volumes_df.reset_index(inplace=True)
	dfs = {'calc_beta': calc_beta_df,'volumes':volumes_df}
	return dfs

def process_stock_prices(d0,d1):

	dfs = import_stock_prices(d0,d1)

	df_calc_beta = dfs['calc_beta'].copy()
	df_returns = df_calc_beta.copy()


	start_row =int(df_returns[df_returns['date']==str(star.prev_trading_date(d0))].index.values -6)

	df_beta= df_returns.copy()
	df_beta5d = df_returns.copy()
	beta= {}

	for i in range(start_row,df_returns.shape[0]):
		for column in df_returns.columns[2:]:
			x = np.array(df_returns['^GSPC'].iloc[i-start_row:i-1]).reshape((-1,1))
			y = np.array(df_returns[column].iloc[i-start_row:i-1])
			try:
				beta[column] = linear_regression(x,y)
			except ValueError:
				print(column,i)


			df_beta[column].iloc[i] = df_returns[column].iloc[i] - beta[column]*df_returns['^GSPC'].iloc[i]
			df_beta5d[column].iloc[i] = df_returns[column].iloc[i-5:i].mean()



	df_beta = df_beta[start_row+6:]
	df_beta5d = df_beta5d[start_row+6:]
	del df_beta['^GSPC']
	del df_beta5d['^GSPC']


	df_volumes = dfs['volumes'].copy()
	df_volumes = df_volumes[start_row+6:]
	del df_volumes['^GSPC']

	assets = df_beta.columns.values.tolist()
	assets.remove('date')
	final_data={}

	for asset in assets:
		remove_list = assets[:]
		remove_list.remove(asset)
		df1 = df_beta.drop(remove_list,axis=1,inplace=False)
		df1.rename(columns={asset:'Beta Adj Return'}, inplace=True)
		df2 = df_beta5d.drop(remove_list,axis=1,inplace=False)
		df2.rename(columns={asset:'5d Avg Beta Adj Return'}, inplace=True)
		df3 = df_volumes.drop(remove_list,axis=1,inplace=False)
		df3.rename(columns={asset:'volume'}, inplace=True)
		df = df1.merge(df2,on='date',how='outer').merge(df3,on='date', how='outer')
		df['Next Day Return'] = df['Beta Adj Return'].shift(-1)
		df=df[:-1]
		st_dev = np.std(df['Next Day Return'])
		df['Classification'] = df['Next Day Return'].apply(calc_classification,stdev1=st_dev)
		final_data[asset]=df

	return final_data