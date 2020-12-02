import pandas as pd
import openpyxl
import stock_tweet_analysis_repo2 as star
import datetime
import pytz
import stock_data_processing as sdp
from sklearn.ensemble import RandomForestClassifier,GradientBoostingClassifier
from openpyxl.utils.dataframe import dataframe_to_rows
import pandas_market_calendars as mcal
import holidays as hd
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib, ssl
import os
pd.options.mode.chained_assignment = None  # disable chain assignment warning

def df_scaler(df):
	for col in df:
		df[col] = (df[col] - df[col].mean())/df[col].std()
	return df	

def remove_tweets_not_containing_ctag(tweet,ctag,l1):
	if not l1:
		return True
	else:
		for item in l1:
			tweet =tweet.replace(item,'')
		return ctag1 in tweet

def send_email(df_reco):
	date_today=datetime.date.today()
	date_today = datetime.datetime.strptime(str(date_today),'%Y-%m-%d')
	html="""\
	<html>
		<body>
			<p>
				This is a list of algorithmically generated recommendations and should not be construed as financial advice. 
				Following any of the below recommendations will expose your money to market risk and may cause financial loss. 
				Any recommended positions are to be hedged vs SP500 index futures according to the six month market-beta
				as specified for each stock in the recommendation table below.  
			</p>
		</body>
	</html>
	{}""".format(df_reco.to_html(index=False))

	recipients = ['mailing_list'] 
	mailing_list = [elem.strip().split(',') for elem in recipients]
	password = 'enter_your_password'
	smtp_server = "smtp.gmail.com"
	sender_email = "enter_youe_email_id"  # Enter your address

	message = MIMEMultipart()
	message["Subject"] = "S&P100 Recommendations For " +  date_today.strftime('%b %d,%Y')
	message["From"] = sender_email
	part = MIMEText(html, "html")
	message.attach(part)

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
filename = os.path.join(dirname,'combined_training_data2.xlsx')
filename1 = os.path.join(dirname, 'historical_data1.xlsx')
filename3 = os.path.join(dirname, 'beta.xlsx')

dict_prev_training_data = pd.read_excel(filename,sheet_name=None)

cashtags = list(dict_prev_training_data.keys())

dt=datetime.date.today()
dt1 = star.prev_trading_date(dt)


data = sdp.process_prices(dt,cashtags)

df_stock_data = data[0]
beta = data[1]

beta_df = pd.DataFrame(beta,index=[0])

writer = pd.ExcelWriter(filename3, engine='openpyxl') 
beta_df.to_excel(writer,index=False)
writer.save()

tz = pytz.timezone('US/Eastern')
datetime_now_est = datetime.datetime.now(tz)
time_cutoff_est = datetime.time(9,30)
time_cutoff_est.replace(tzinfo=tz)


date_finish = datetime_now_est.date()
date_start = star.prev_trading_date(date_finish)
datetime_start = datetime.datetime(date_start.year,date_start.month,date_start.day,time_cutoff_est.hour,time_cutoff_est.minute,time_cutoff_est.second)

#if time_cutoff_est<datetime_now_est.time():
#	date_start = date_finish
#	datetime_start = datetime.datetime(date_start.year,date_start.month,date_start.day,time_cutoff_est.hour,time_cutoff_est.minute,time_cutoff_est.second)

datetime_start = tz.localize(datetime_start)


dict_data_appended={}
df_dict_data_appended={}

for cashtag in cashtags:
	df= star.tweet_scraper(date_start,cashtag)
	df['datetime'] = pd.to_datetime(df.drop(['tweet'],axis=1,inplace=False),utc=True)
	df['datetime'] = df['datetime'].dt.tz_convert('US/Eastern')
	df.drop(['year','month','day','hour','minute','second'],axis=1,inplace=True)
	df = df[df['datetime']>=datetime_start]

	#removing tweets that contain, for example, $MSFFT but not $MS when cashtag=MS
	ctag1 = '$' + cashtag
	l1 = [item for item in ['$' + element for element in cashtags] if ctag1 in item] 
	if ctag1 in l1:
		l1.remove(ctag1)
	df = df[df['tweet'].apply(remove_tweets_not_containing_ctag,args=(ctag1,l1))]

	df = star.tweet_cleaner(df)
	df = star.sentiment_analysis(df)
	avg_sentiment= df['sentiment'].mean()
	no_of_tweets = df['sentiment'].count()

	dict_data_appended = {'date'  : [str(dt1)], 'average sentiment' : [avg_sentiment],'number of tweets':[no_of_tweets],'change in sentiment': [avg_sentiment-dict_prev_training_data[cashtag]['average sentiment'].iloc[-1]]}
	df_temp = pd.DataFrame(dict_data_appended)
	df_stock_data[cashtag]['date'].apply(str)
	df_dict_data_appended[cashtag] = df_temp.merge(df_stock_data[cashtag],on='date',how='outer')
	#print(cashtag)



## check whether training data for today (with date T-1) exists in training data.If yes, overwrite. If no, write new line with Next Day Return and Classification =0

for cashtag,df in dict_prev_training_data.items():
	list_of_dates = str(df['date'].values.tolist())
	if str(df_dict_data_appended[cashtag]['date'].iloc[0]) in list_of_dates:
		df = df.iloc[:-1]
	df_dict_data_appended[cashtag]['Next Day Return'] = [0]
	df_dict_data_appended[cashtag]['Classification'] = [0]
	dict_prev_training_data[cashtag] = df.append(df_dict_data_appended[cashtag],ignore_index=True)


writer = pd.ExcelWriter(filename, engine='openpyxl') 
for asset, df in dict_prev_training_data.items():
	df.to_excel(writer, sheet_name=asset,index=False)
writer.save()


dfs_hist = pd.read_excel(filename1,sheet_name=None)

#calculate prediction for today
df_ypred =pd.DataFrame({'date':[str(dt)]})

for cashtag in cashtags:
	df_scaled= df_scaler(dict_prev_training_data[cashtag].drop(['date','5d Avg Beta Adj Return','Next Day Return','Classification'],axis=1).copy())
	X_train=df_scaled.iloc[:-1]
	X_test = df_scaled.iloc[-1:]
	y_train = dict_prev_training_data[cashtag]['Classification'].iloc[:-1]
	model =RandomForestClassifier()
	try:
		model.fit(X_train,y_train)
		y_pred = model.predict(X_test)
	except:
		y_pred=0	
	df_ypred[cashtag] = int(y_pred)

df_reco = pd.DataFrame(columns=['Symbol','Beta','Recommendation'])

df_ypred1= df_ypred.drop(['date'],axis=1).copy()

for column in df_ypred1.columns:
	dict_row={}
	dict_row['Symbol'] = column
	dict_row['Beta'] = beta[column]
	dict_row['Recommendation'] = df_ypred1[column].iloc[0]
	df_reco = df_reco.append(dict_row,ignore_index=True)

df_reco = df_reco[df_reco['Recommendation']!=0]
df_reco = df_reco.sort_values(by =['Recommendation'])
df_reco.replace(-2,'Strong Sell',inplace=True)
df_reco.replace(-1,'Sell',inplace=True)
df_reco.replace(1,'Buy',inplace=True)
df_reco.replace(2,'Strong Buy',inplace=True)

send_email(df_reco)


#check if prediction for today exists. If yes, overwrite. If no, wrte new line.

wb =  openpyxl.load_workbook(filename1)
ws = wb['predictions']
lastrow = ws.max_row


list_of_dates = str(dfs_hist['predictions']['date'].values.tolist())

if str(dt) in list_of_dates:
	ws.delete_rows(lastrow,1)
for rows in dataframe_to_rows(df_ypred, index=False, header=False):
	ws.append(rows)

wb.save(filename1)


