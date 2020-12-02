import snscrape.modules
import pandas as pd
import re
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import requests
from bs4 import BeautifulSoup
import openpyxl
from openpyxl import load_workbook
import datetime 
import pandas_market_calendars as mcal
import holidays as hd
import pytz

def get_cashtags():
	#getting the list of all S&P500 constituents
	table = pd.read_html('https://en.wikipedia.org/wiki/S%26P_100')
	df_companies_info=table[2]

	# df_companies_info['Date first added'].apply(datetime_from_date)


	assets = list(df_companies_info['Symbol'])
	assets.remove('GOOGL')
	assets.remove('DOW')
	return assets

def tweet_scraper(start,cashtag):




	cashtag=str(cashtag)
	cashtag1 = '$' + cashtag

	df_tweets = pd.DataFrame(columns=['year','month','day','hour','minute','second','tweet'])

	for i in snscrape.modules.twitter.TwitterSearchScraper(cashtag1 + ' since:' + str(start)  + ' lang:en').get_items():
		y = i.date.year
		m = i.date.month
		d = i.date.day
		h = i.date.hour
		mi = i.date.minute
		s = i.date.second
		dict_row={'year': y, 'month': m, 'day': d, 'hour': h, 'minute': mi, 'second': s, 'tweet': i.content}
		df_tweets = df_tweets.append(dict_row,ignore_index=True)
	

		        		
	return df_tweets			

def clean(val):
	val = str(val)
	val = re.sub(r"http\S+", "", val) 
	val = re.sub(r'pic.twitter.com/[\w]*',"", val)
	val = re.sub('[^a-zA-Z0-9\n\s\.?!-]', '', val)
	return val

def calc_cashtags(ctag):
	a = list(str(ctag))
	number_of_cashtags= a.count('$')
	return number_of_cashtags


def tweet_cleaner(df):



	# cleaning the tweet- removing links and special characters
	df['number_of_cashtags'] = df['tweet'].apply(calc_cashtags)
	

	# removing tweets which do not contain JPM and have equal to or more than 5 cashtags : highly liekly to be irrelevant 

	df1 = df.drop(df[(df.number_of_cashtags>=5)].index) # & (cashtag not in df.cleaned_tweet)].index)

	#removes duplicate rows

	df1.drop_duplicates(subset=None, keep='first', inplace=True)
	df1.drop('number_of_cashtags', axis=1, inplace=True)
	df1['cleaned_tweet'] = df1['tweet'].apply(clean)
	df1.drop('tweet', axis=1, inplace=True)
	#opfile = str(cashtag) + "_cleaned_tweets.csv"
	#df1.to_csv(opfile)
	return df1

def sentiment_analysis(df):
	# initialting the sentiment analyzer
	analyser = SentimentIntensityAnalyzer()

	# function to analyze sentiment of a tweet 
	def tweet_sentiment_analyzer(tw):
		tw = str(tw)
		score = analyser.polarity_scores(tw)
		return score.get('compound')

	def link_sentiment_analyzer(l):
		l = str(l)
		if l=="[]":
			var =str(0)
		else:
			try:
				url = l[2:-2]
				res = requests.get(url)
				html_page = res.content
				soup = BeautifulSoup(html_page, 'html.parser')
				text = str(soup.find_all('p'))

				score = analyser.polarity_scores(text)
				var = str(score.get('compound'))
			except:
				var=""
		return var


	df['sentiment'] = df['cleaned_tweet'].apply(tweet_sentiment_analyzer)

	# link sentiment ana;ysis works but is very slow for thousands of links
	#df['link_sentiment'] = df['urls'].apply(link_sentiment_analyzer)

	return df

# sentiment analysis by date

#gets next trading date from specified datetime
def next_trading_date(dt):
	nyse = mcal.get_calendar('NYSE')
	holidays = nyse.holidays()
	holidays_nyse = list(holidays.holidays[:])

	one_day = datetime.timedelta(days=1)
	next_date = dt + one_day
	while next_date.weekday() in hd.WEEKEND or next_date in holidays_nyse:
		next_date += one_day
	return next_date

#gets next trading date from specified date
def prev_trading_date(dt):
	nyse = mcal.get_calendar('NYSE')
	holidays = nyse.holidays()
	holidays_nyse = list(holidays.holidays[:])

	one_day = datetime.timedelta(days=1)
	prev_date = dt - one_day
	while prev_date.weekday() in hd.WEEKEND or prev_date in holidays_nyse:
		prev_date -= one_day
	return prev_date

def to_dt(date1,time1):
	dt =  datetime.datetime(date1.year,date1.month,date1.day,time1.hour,time1.minute,time1.second)
	timezone = pytz.timezone('US/Eastern')
	dt_tz = timezone.localize(dt)
	return dt_tz

def utc_to_est(dt):
	est = pytz.timezone('US/Eastern')
	utc = pytz.utc
	fmt = '%Y-%m-%d %H:%M:%S'
	return dt.astimezone(est).strftime(fmt)


def sentiment_by_date(df):

	#df.rename(columns={'min': 'minute', 'sec': 'second'},inplace=True)
	df['datetime'] = pd.to_datetime(df.drop(['cleaned_tweet','sentiment'],axis=1,inplace=False),utc=True)
	df['datetime'] = df['datetime'].dt.tz_convert('US/Eastern')
	df.drop(df.columns[0:6],axis=1,inplace=True)
	df.sort_values('datetime', ascending=False, inplace=True)
	dt1 = datetime.datetime(2020,10,22,0,0,0)
	localtz = pytz.timezone('US/Eastern')
	dt1 = dt1.replace(tzinfo=localtz)
	df = df[df['datetime']>=dt1]
	start_datetime = df['datetime'].iloc[-1]
	start_datetime  = to_dt(start_datetime.date(),datetime.time(9))
	next_datetime = to_dt(next_trading_date(start_datetime.date()),datetime.time(9))


	var = True
	columns=['date','average sentiment','number of tweets']
	df2 = pd.DataFrame(columns=columns)

	while var:
		avg_sentiment = df[(df['datetime']>=start_datetime) & (df['datetime']<next_datetime)]['sentiment'].mean()
		num_tweets = df[(df['datetime']>=start_datetime) & (df['datetime']<next_datetime)]['cleaned_tweet'].count()
		new_row = {'date' : start_datetime.date(), 'average sentiment': avg_sentiment,'number of tweets':num_tweets}
		df2 = df2.append(new_row,ignore_index=True)
		start_datetime = next_datetime
		next_datetime = to_dt(next_trading_date(start_datetime.date()),datetime.time(9))

		if start_datetime>df['datetime'].iloc[0]:
			var=False
	
	df2.fillna(0,inplace=True)
	return df2


