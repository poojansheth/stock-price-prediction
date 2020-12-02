import pandas as pd
import openpyxl
import stock_tweet_analysis_repo2 as star
import datetime
import pytz
import stock_data_processing as sdp
from openpyxl.utils.dataframe import dataframe_to_rows
from dateutil.relativedelta import relativedelta
from yahoofinancials import YahooFinancials
import numpy as np
import pandas_market_calendars as mcal
import holidays as hd
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib, ssl
import io
from email.mime.image import MIMEImage
import matplotlib.pyplot as plt
from pathlib import Path
pd.options.mode.chained_assignment = None  # disable chain assignment warning

def send_email(df_plot,df_perf):
	date_today=datetime.date.today()
	date_today = datetime.datetime.strptime(str(date_today),'%Y-%m-%d')
	html="""\
	<html>
		<body>
			<p>
				Perfomrance summary for today's recommendations-
			</p>
		</body>
	</html>
	{}""".format(df_perf.to_html(index=False))

	recipients = ['prabhavb@gmail.com','poojan.sheth17@gmail.com'] 
	mailing_list = [elem.strip().split(',') for elem in recipients]
	password = 'r00mb@r00mb@'
	smtp_server = "smtp.gmail.com"
	sender_email = "python.emails.poojan@gmail.com"  # Enter your address
	receiver_email = "muggi.14@gmail.com"  # Enter receiver address

	message = MIMEMultipart()
	message["Subject"] = "Performance update for " +  date_today.strftime('%b %d,%Y')
	message["From"] = sender_email
	part1 = MIMEText(html, "html")
	message.attach(part1)

	buf = io.BytesIO()
	df_plot.plot(x ='date', y=['strategy','SP500'], kind = 'line')
	plt.savefig(buf, format = 'png')
	buf.seek(0)
	part2 = MIMEImage(buf.read())
	message.attach(part2)

	context = ssl.create_default_context()
	with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
		server.login(sender_email, password)
		server.sendmail(sender_email, mailing_list, message.as_string())


date_today = datetime.date.today()

nyse = mcal.get_calendar('NYSE')
holidays = nyse.holidays()
holidays_nyse = list(holidays.holidays[:])

if date_today.weekday() in hd.WEEKEND or date_today in holidays_nyse:
	raise SystemExit(0)

dirname = os.getcwd()
p = Path(os.path.abspath(__file__)).parents[1]
filename = os.path.join(p, 'Initial scraping','tweet data','combined_training_data2.xlsx')
filename1 = os.path.join(dirname, 'historical_data1.xlsx')
filename3 = os.path.join(dirname, 'beta.xlsx')


beta = pd.read_excel(filename2)
dfs_hist = pd.read_excel(filename1,sheet_name=None)
dfs_training = pd.read_excel(filename3,sheet_name=None)

assets = beta.columns.values.tolist()
assets.insert(0,'^GSPC')

date_today = datetime.date.today()
date_end = star.next_trading_date(date_today)         

yahoo_financials = YahooFinancials(assets)

data = yahoo_financials.get_historical_price_data(start_date=str(date_today), 
                                              end_date=str(date_end), 
                                              time_interval='daily')

a0=assets[0]
returns_df = pd.DataFrame({a0: {x['formatted_date']: (x['adjclose'] - x['open'])/x['open'] for x in data[a0]['prices']}})
returns_df.index.name='date'
assets.remove('^GSPC')

for a in assets:
	try:
		returns_df1 = pd.DataFrame({a: {x['formatted_date']: (x['close'] - x['open'])/x['open'] for x in data[a]['prices']}})
		returns_df1.index.name='date'
		returns_df = pd.merge(returns_df,returns_df1,on='date',how='outer')

	except KeyError:
		pass

beta_adj_returns_df = returns_df.copy()
beta_adj_returns_df.drop('^GSPC',axis=1,inplace=True)

for a in assets:
	beta_adj_returns_df[a].iloc[0] = returns_df[a].iloc[0] - beta[a].iloc[0]*returns_df['^GSPC'].iloc[0]
	dfs_training[a]['Next Day Return'].iloc[-1] = returns_df[a].iloc[0] - beta[a].iloc[0]*returns_df['^GSPC'].iloc[0]
	dfs_training[a]['Classification'].iloc[-1] = sdp.calc_classification(dfs_training[a]['Next Day Return'].iloc[-1],dfs_training[a]['Next Day Return'].std())

positions = dfs_hist['predictions'].drop('date',axis=1).iloc[-1:].values.tolist()
positions1 = dfs_hist['predictions'].drop('date',axis=1).iloc[-1:].copy()  # to create table to send with email
positions = np.array(positions)

positions = positions/(np.sum(np.absolute(positions)))

returns = beta_adj_returns_df.iloc[-1:].values.tolist()
returns1 = beta_adj_returns_df.iloc[-1:]
returns = np.array(returns)

daily_return = 1 + np.inner(returns,positions)[0][0]

hist_perf_df = dfs_hist['historical performance']

cumulative_return  = daily_return*float(hist_perf_df['strategy'].iloc[-1])

date_hist_perf_bmark = datetime.date(2020,6,29)

sp500 ='^GSPC'
yahoo_financials = YahooFinancials(sp500)

data = yahoo_financials.get_historical_price_data(start_date=str(date_hist_perf_bmark), 
                                              end_date=str(date_end), 
                                              time_interval='daily')


returns_sp500_df = pd.DataFrame({sp500: {x['formatted_date']: x['adjclose'] for x in data[sp500]['prices']}})

cumulative_sp500_return = returns_sp500_df['^GSPC'].iloc[-1]/returns_sp500_df['^GSPC'].iloc[0]

hist_perf_append_df = pd.DataFrame({'date': [str(date_today)], 'strategy': [cumulative_return], 'SP500':[cumulative_sp500_return]})

# performance table to be sent out with email
df_perf = pd.DataFrame(columns=['Symbol','Recommendation','Beta-adjusted return'])
for column in positions1.columns:
	dict_append = {'Symbol': column,'Recommendation':positions1[column].iloc[0],'Beta-adjusted return':str(round(100*returns1[column].iloc[0],2)) +'%'}
	df_perf = df_perf.append(dict_append,ignore_index=True)
df_perf = df_perf[df_perf['Recommendation']!=0]
df_perf = df_perf.sort_values(by =['Recommendation'])
df_perf.replace(-2,'Strong Sell',inplace=True)
df_perf.replace(-1,'Sell',inplace=True)
df_perf.replace(1,'Buy',inplace=True)
df_perf.replace(2,'Strong Buy',inplace=True)

dict_append=pd.DataFrame({'Symbol': ['Strategy Daily Return','S&P500 Daily Return'],
						  'Recommendation': ['',''],
						  'Beta-adjusted return':[str(round(100*(daily_return-1),2)) + '%', str(round(100*(returns_sp500_df['^GSPC'].iloc[-1]/returns_sp500_df['^GSPC'].iloc[-2] -1),2))+'%']})

df_perf = df_perf.append(dict_append,ignore_index=True)


wb =  openpyxl.load_workbook(filename1)
ws = wb['historical performance']
lastrow = ws.max_row


list_of_dates = str(dfs_hist['historical performance']['date'].values.tolist())

if str(date_today) in list_of_dates:
	ws.delete_rows(lastrow,1)
for rows in dataframe_to_rows(hist_perf_append_df, index=False, header=False):
	ws.append(rows)

wb.save(filename1)
dfs_hist = pd.read_excel(filename1,sheet_name=None)
df_plot = dfs_hist['historical performance']

send_email(df_plot,df_perf)


writer = pd.ExcelWriter(filename3, engine='openpyxl') 
for asset, df in dfs_training.items():
	df.to_excel(writer, sheet_name=asset,index=False)
writer.save()
