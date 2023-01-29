from flask import Flask, render_template, request, url_for
import mysql.connector as conn
import time, datetime
import pandas as pd
import os
from pymongo import MongoClient


app = Flask(__name__)

@app.route("/", methods=['GET','POST'])
def index():

	if request.method == 'POST':
		#fetch the data from the web page
		request_ts = str(datetime.datetime.now())
		host = request.form['host']
		user = request.form['user']
		passwd = request.form['passwd']
		db = request.form['db']
		src_query = request.form['src_query']
		tgt_query = request.form['tgt_query']

		try:
			start_time = time.time()
			
			# connect to DB
			cnx = conn.connect(host = host, user = user,
					passwd = passwd, database = db)
			cur = cnx.cursor()

			# execute SQL queries and create src and tgt dataframes
			cur.execute(src_query)
			res = cur.fetchall()
			df_src = pd.DataFrame(res, columns=[col[0] for col in cur.description])

			cur.execute(tgt_query)
			res = cur.fetchall()
			df_tgt = pd.DataFrame(res, columns=[col[0] for col in cur.description])

			# create target directory (inside container) to store result files
			tgt_dir = 'tgt'+'/'+request_ts.replace(' ','_').replace(':','-')
			os.system('mkdir {}'.format(tgt_dir))

			# create dataframes with mismatches and write to target as csv files
			src_diff_tgt = df_diff(df_src, df_tgt, which='left_only')
			src_diff_tgt.to_csv(tgt_dir+'/src_diff_tgt.csv', index=False)
			tgt_diff_src = df_diff(df_src, df_tgt, which='right_only')
			tgt_diff_src.to_csv(tgt_dir+'/tgt_diff_src.csv', index=False)
			msg = 'Successful!!'

			# check total time taken except mongo-db logging
			duration = round((time.time()-start_time), 3)

			# dictionary with statistics for comparison
			mydict = { 
							"Req_ts": request_ts, "Host": host, "DB": db,
							"SRC_query": src_query, "TGT_query": tgt_query,
							"Match": len(df_src)-len(src_diff_tgt), "SRC_diff_TGT": len(src_diff_tgt),
							"TGT_diff_SRC": len(tgt_diff_src), "Duration": duration 
					}

			# log stats to mongodb
			mongo_log(mydict)

		except Exception as e:
			msg = 'Error=====>{}'.format(e)

		finally:
			print('Closing DB conn....', flush=True)
			cnx.close()


			
		return render_template('index.html', duration=duration, msg=msg, mydict=mydict)
	#if method=GET (when we just reload the page or visit for first time)
	return render_template('index.html', mydict={})


def mongo_log(mydict):
	''' Log the compare statistics into MongoDB collection'''
	try:
		# connect to mongo-db
		# we have to use @localhost:27018 in place of @mongodb if app.py not running as container in same network
		client = MongoClient("mongodb://admin:password@mongodb/")

		# create DB and collection (table) if not exist
		mydb = client["db-compare"]
		mycol = mydb["result"]

		# insert compare stats as new document (record). Every doc will have unique id 
		# if not specified manually then auto-generated id
		x = mycol.insert_one(mydict)
		if x.acknowledged == True:
			print('Logged successfuly!!', flush=True)

	except Exception as e:
		msg = 'Mongo Error=====>{}'.format(e)


def df_diff(df1, df2, which=None):
	"""Find rows which are different between two DataFrames."""
	comparison_df = df1.merge(df2, indicator=True, how='outer')
	diff_df = comparison_df[comparison_df['_merge'] == which].drop('_merge', axis=1)
	return diff_df


if __name__ == '__main__':
	app.run(host="0.0.0.0", port=3000, debug=True)