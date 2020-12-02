import pandas as pd
import stock_tweet_analysis_repo as star
import stock_data_processing as sdp
import datetime
import os
from pathlib import Path

#Set the date range. This script scrapes tweets for SP100 stocks (except BRK.B,COF,DD,GOOGL,RTX) from 1/1/19 to today 
date_start = datetime.date(2018,9,1)
date_end=datetime.date(2018,12,21)
#date_end =datetime.date.today()

dirname = os.getcwd()

headers=['year','month','day','hour','min','sec','tweet']
df = pd.DataFrame(columns=headers)

cashtags = star.get_cashtags()


for cashtag in cashtags:
	d1 = date_end
	d0 = d1 - datetime.timedelta(days=1)
	try:
		while d0 >= date_start:
			df = star.tweet_scraper(d0,d1,cashtag,df)
			d1=d0
			d0 = d0 - datetime.timedelta(days=1)
	except:
		print(cashtag + ' tweets not scraped')
		continue
	print(cashtag + ' tweets scraped')
	filename = os.path.join(dirname,'tweet data',cashtag +'.xlsx')	
	df.to_excel(filename)	


# getting stock data and storing it in /tweet data/stock_data.xlsx

dfs_price = sdp.process_stock_prices(date_start,date_end)

#processing scraped tweets into daily sentiment data

dfs_sentiment = star.process_tweet_sentiment_data()


# combining the stock and tweet data to generate training data

dfs_merged = {}

for cashtag,df in dfs_sentiment.items():
	df1 = dfs_sentiment[cashtag]
	df2=dfs_price[cashtag]
	df1['date'] = df1['date'].astype(str)
	df2['date'] = df2['date'].astype(str)
	df1.drop(df1.index[:1], inplace=True)
	df3 = df1.merge(df2,how='inner',on='date')
	dfs_merged[cashtag]=df3


p = Path(os.path.abspath(__file__)).parents[1]
filename = os.path.join(p, 'Ongoing prediction','combined_training_data2.xlsx')
writer = pd.ExcelWriter(filename, engine='openpyxl') 
for asset, df in dfs_merged.items():
	df.to_excel(writer, sheet_name=asset,index=False)

writer.save()



