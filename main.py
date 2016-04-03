import sys
import feedparser
import json
import pymongo
import subprocess
import time
import string
import urllib
import csv
import os
import itertools
import random
from multiprocessing import Pool, Manager
from string import punctuation
from shutil import copyfile
import nltk
import os.path
import datetime
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from string import punctuation
from pandas import  date_range
from pandas import  bdate_range
from datetime import datetime
from pandas.tseries.offsets import DateOffset, BDay
from yahoo_finance import Share

try:
	client = pymongo.MongoClient(connect = False)
	cdb = client.Companydb
	cdb.createCollection( "Companydb", { } )
except:
	print "Company database already exists"
try:
	ddb = client.Dictdb
	ddb.createCollection( "Dictionarydb", { } )
except:
	print "Dictionary database already exists"
	
def printfeeds (RSSfeeds):
	for feed in RSSfeeds:
		print feed.url
		for entry in feed.entries:
			print feed.url,
			print entry.title,
			print entry.author,
			print entry.summary,	
			print entry.link,
			print entry.published,
			print time.time(),
			print getsentiment(entry.summary)
	return

def getimportantsentiment (statement, importantwords):
	words = ''.join(c for c in statement if c not in punctuation).lower().split()
	numwords = 0
	x = 0
	importantwords = importantwords.split(',')
	for word in words:
		if ddb.dictionary.find({"word": word}).count() != 0:
			numwords += 1
			dictword = ddb.dictionary.find_one({"word": word.encode('utf-8')})
			temp = 1
			for importantword in importantwords:
				if word == importantword:
					temp = 2
			x += temp*float(int(dictword["positive"])-int(dictword["negative"]))/int(dictword["seen"])
	if numwords != 0:
		x /= numwords	
	return x
	
def getsentiment (statement):
	words = ''.join(c for c in statement if c not in punctuation).lower().split()
	numwords = 0
	x = 0
	for word in words:
		if ddb.dictionary.find({"word": word}).count() != 0:
			numwords += 1
			dictword = ddb.dictionary.find_one({"word": word.encode('utf-8')})
			x += float(int(dictword["positive"])-int(dictword["negative"]))/int(dictword["seen"])
	if numwords != 0:
		x /= numwords	
	return x		

def listsentiments ():
	companies = getcompanies()
	company = random.choice(companies)
	print company[1]
	feed = feedparser.parse("http://finance.yahoo.com/rss/headline?s="+company[1])
	length = len(feed)
	for entry in feed.entries:
		if 'summary' in entry and entry.summary != "":
			print entry.summary.encode('utf-8','ignore') + "\n" + str(getsentiment(entry.summary.encode('utf-8','ignore')))
		elif 'title' in entry and entry.title != "":
			print entry.title.encode('utf-8','ignore') + "\n" + str(getsentiment(entry.title.encode('utf-8','ignore')))

def printdictionary ():
	for document in ddb.dictionary.find():
		print document["word"]
	print ddb.dictionary.find().count()

def resetdictionary ():
	client.drop_database('Dictdb')
	try:
		ddb = client.Dictdb
		ddb.createCollection( "Dictionarydb", { } )
	except:
		i = 0
#		print "still fucked m80"
	sentimentdictionary = open('sentimentdictionary', 'a')
	sentimentdictionary.close()
	sentimentdictionary = open('sentimentdictionary', 'r+')
	lines = sentimentdictionary.readlines()
	dictwords = []
	for line in lines:
		temp = line.rstrip('\n').split(',')
		dictwords.append(temp)
	sentimentdictionary.close()
	for dictword in dictwords:
		if ddb.dictionary.find({"word": dictword}).count() == 0:
			post = { 
			"word": dictword[0],
			"seen": dictword[1],
			"positive": dictword[2],
			"negative": dictword[3],
			}
			ddb.dictionary.insert_one(post)
	return

def autotrain ():
	gettime = time.time()
	companies = getcompanies()

	pool = Pool(processes=50)
	client.close()
	pool.imap_unordered(autotrainer, companies)
	pool.close()
	pool.join()
	gettime = time.time() - gettime
	print "Total time to complete: " + str(gettime)
	print "now testing database"
	for company in companies:
		feed = feedparser.parse("http://finance.yahoo.com/rss/headline?s="+company[1])
		length = len(feed)
		for entry in feed.entries:
			if 'summary' in entry and entry.summary != "":
				print entry.summary.encode('utf-8') + "\n" + str(getsentiment(entry.summary.encode('utf-8','ignore')))
			elif 'title' in entry and entry.title != "":
				print entry.title.encode('utf-8') + "\n" + str(getsentiment(entry.title.encode('utf-8','ignore')))
		
def autotrainer (company):
	client = pymongo.MongoClient()
	ddb = client.Dictdb

	feed = feedparser.parse("http://finance.yahoo.com/rss/headline?s="+company[1])
	for entry in feed.entries:
		if 'summary' in entry and entry.summary != "":
			words = ''.join(c for c in entry.summary if c not in punctuation).lower().split()
			statement = entry.summary
		elif 'title' in entry and entry.title != "":
			words = ''.join(c for c in entry.title if c not in punctuation).lower().split()
			statement = entry.title
		else:
			break
		if getsentiment(statement) >= 1.0/3:
			sentiment = 'p'
		elif getsentiment(statement) > -1.0/3:
			sentiment = 'a'
		else:
			sentiment = 'n'
		for word in words:
			if ddb.dictionary.find({"word": word.encode('utf-8','ignore')}).count() == 0:
				if sentiment == 'p':
					post = { 
					"word": word.encode('utf-8','ignore'),
					"seen": 1,
					"positive": 1,
					"negative": 0,
					}
				elif sentiment == 'n':
					post = { 
					"word": word.encode('utf-8','ignore'),
					"seen": 1,
					"positive": 0,
					"negative": 1,
					}
				else:
					post = { 
					"word": word.encode('utf-8','ignore'),
					"seen": 1,
					"positive": 0,
					"negative": 0,
					}
				ddb.dictionary.insert_one(post)
			else:
				dictword = json.load(ddb.dictionary.find_one({"word": word.encode('utf-8','ignore')}))
				if sentiment == 'p':
					ddb.dictionary.update_one({"word": word}, {"$set": {"seen": dictword.seen+1, "positive": dictword.positive+1, "negative": dictword.negative}})
				elif sentiment == 'n':
					ddb.dictionary.update_one({"word": word}, {"$set": {"seen": dictword.seen+1, "positive": dictword.positive, "negative": dictword.negative+1}})
				else:
					ddb.dictionary.update_one({"word": word}, {"$set": {"seen": dictword.seen+1, "positive": dictword.positive, "negative": dictword.negative}})
	client.close()
	return

def trainer ():
	sentimentdictionary = open('sentimentdictionary', 'a')
	sentimentdictionary.close()
	sentimentdictionary = open('sentimentdictionary', 'r+')
	lines = sentimentdictionary.readlines()
	dictwords = []
	for line in lines:
		temp = line.rstrip('\n').split(',')
		dictwords.append(temp)
		
	companies = getcompanies()
	random.shuffle(companies)
	for company in companies:
		feed = feedparser.parse("http://finance.yahoo.com/rss/headline?s="+company[1])
		for entry in feed.entries:
			if 'summary' in entry and entry.summary != "":
				words = ''.join(c for c in entry.summary if c not in punctuation).lower().split()
				sentiment = raw_input("\"" + entry.summary.encode('utf-8','ignore') + "\"\n")
			elif 'title' in entry and entry.title != "":
				words = ''.join(c for c in entry.title if c not in punctuation).lower().split()
				sentiment = raw_input("\"" + entry.title.encode('utf-8','ignore') + "\"\n")
			else:
				break
			if sentiment == 'e':
				break
			for word in words:

				exists = False
				for dictword in dictwords:
					if word.encode('utf-8','ignore') == dictword[0]:
						exists = True
						break
					else:
						continue
				if exists == True:
					dictword[1] = int(dictword[1]) + 1
					if sentiment == 'p':
						dictword[2] = int(dictword[2]) + 1
					elif sentiment == 'n':
						dictword[3] = int(dictword[3]) + 1
				else:
					if sentiment == 'p':
						dictwords.append([word.encode('utf-8','ignore'), 1, 1, 0])
					elif sentiment == 'n':
						dictwords.append([word.encode('utf-8','ignore'), 1, 0, 1])
					elif sentiment == 'a':
						dictwords.append([word.encode('utf-8','ignore'), 1, 0, 0])
		if sentiment == 'e':
			break
	sentimentdictionary.close()
	os.remove('sentimentdictionary')
	sentimentdictionary = open('sentimentdictionary', 'w')
	for dictword in dictwords:
		if ddb.dictionary.find({"word": dictword}).count() == 0:
			post = { 
			"word": dictword[0],
			"seen": dictword[1],
			"positive": dictword[2],
			"negative": dictword[3],
			}
			ddb.dictionary.insert_one(post)
		else:
			dictword = json.load(ddb.dictionary.find_one({"word": word.encode('utf-8','ignore')}))
			if sentiment == 'p':
				ddb.dictionary.update_one({"word": word}, {"$set": {"seen": dictword.seen+1, "positive": dictword.positive+1, "negative": dictword.negative}})
			elif sentiment == 'n':
				ddb.dictionary.update_one({"word": word}, {"$set": {"seen": dictword.seen+1, "positive": dictword.positive, "negative": dictword.negative+1}})
			else:
				ddb.dictionary.update_one({"word": word}, {"$set": {"seen": dictword.seen+1, "positive": dictword.positive, "negative": dictword.negative}})
		print>>sentimentdictionary, dictword[0]+","+str(dictword[1])+","+str(dictword[2])+","+str(dictword[3])
	sentimentdictionary.close()
	return



def importantwords (ticker):	
	feed = feedparser.parse("http://finance.yahoo.com/rss/headline?s="+ticker)
	fst=''
	for entry in feed.entries:
	   
		if 'title' in entry and entry.title != "":
			titles =''.join(c for c in entry.title if c not in punctuation).lower()
			titles= titles.encode('ascii', 'ignore')
			titles=str(titles)
			titles_tok = word_tokenize(titles)
			stop_words = set(stopwords.words("english"))
			filtered_titles = [w for w in titles_tok if not w in stop_words]
			fs= str(filtered_titles)
			fst=fs+fst
		else:
			break
	fst_list = fst.split(",")
	return fst_list

def deldb ():
	client.drop_database('Companydb')
	client.drop_database('Dictdb')
	return

def getrating (company):
	feed = feedparser.parse("http://finance.yahoo.com/rss/headline?s="+company[1])
	rating = 0
	length = len(feed)
	importantwords = importantwords(company)
	for entry in feed.entries:
		if 'summary' in entry and entry.summary != "":
			rating += getimportantsentiment(entry.summary.encode('utf-8','ignore'),importantwords);
		elif 'title' in entry and entry.title != "":
			rating += getimportantsentiment(entry.title.encode('utf-8','ignore'),importantwords);
		else:
			length -= 1
	if (length != 0):
		rating = rating/length
	return rating

def analyzestockdata (data):
	ticker = data[0]
	ask = data[1]
	bid = data[2]
	opn = data[3]
	clse = data[4]
	change = data[5]
	daylow = data[6]
	dayhigh = data[7]
	yearlow = data[8]
	volume = data[9]
	asksize = data[10]
	bidsize = data[11]
	return (float(clse)-float(opn))/float(opn);

def getstockrating (company):
	tempdir = r'./temp' 
	if not os.path.exists(tempdir):
		os.makedirs(tempdir)
	rating = 0
	urllib.urlretrieve ("http://finance.yahoo.com/d/quotes.csv?s="+company[1]+"&f=sabopc1ghjkva5b6", "./temp/"+company[1]+"tempquote.csv")
	with open("./temp/"+company[1]+"tempquote.csv", 'r') as doc:
		reader = csv.reader(doc)
		for row in reader:
			rating = analyzestockdata(row)
	os.remove("./temp/"+company[1]+"tempquote.csv")
	return rating
#	urllib.urlretrieve ("http://finance.yahoo.com/d/quotes.csv?s="+tempstr+"&f=abb2b3poc1vv6k2p2c8c3ghk1ll1t8w1w4p1mm2kjj5k4j6k5wva5b6k3a2ee7e8e9b4j4p5p6rr2r5r6r7s7ydr1qd1d2t1m5m6m7m8m3m4g1g3g4g5g6vj1j3f6nn4ss1xj2t7t6i5l2l3v1v7s6", "./temp/temp.csv")	

def companyupdate (company):
	client2 = pymongo.MongoClient(connect=False)
	cdb = client2.Companydb
	ddb = client2.Dictdb

	if cdb.companies.find({"company": company[0]}).count() == 0:
		rating = getrating(company)
		post = { 
		"company": company[0],
		"symbol": company[1],
		"sector": company[2],
		"industry": company[3],
		"rating": rating,
		"updated": time.time(),
		"change": change(company[1])
		}
		cdb.companies.insert_one(post)
#		print "\"" + company[0] + "\" added. rating = " + str(rating)
	else:
		rating = getrating(company)
		result = cdb.companies.update_one({"company": company}, {"$set": {"rating": rating, "updated": time.time(), "change": change(company[1])}})
#		print "\"" + company[0] + "\" already exists. New rating = " + str(rating)
	client2.close()

def batchcompanyupdate ():
	gettime = time.time()
	pool = Pool(processes=20)
	companies = []
	companies = getcompanies()
	print "A total of " + str(len(companies)) + " companies to update"
	
	client.close()
	pool.imap_unordered(companyupdate, companies)
	
	gettime = time.time() - gettime
	print "Total time to complete: " + str(gettime)

def getcompanies ():
	companies = []
	tempdir = r'./temp' 
	if not os.path.exists(tempdir):
		os.makedirs(tempdir)
	NASDAQlistings = open('nasdaq', 'r')
	lines = NASDAQlistings.readlines()
	for line in lines:
		urllib.urlretrieve (line, "./temp/templistings.csv")
		with open("./temp/templistings.csv", 'r') as doc:
			reader = csv.reader(doc)
			reader. next()	#skip first line
			for row in reader:
				company = []
				company.append(row[1])	#company name
				company.append(row[0])	#company ticker
				company.append(row[6])	#company sector
				company.append(row[7])	#company industry
				companies.append(company)
		os.remove("./temp/templistings.csv")
	return companies

def printcompanyinfo (name):
	cursor = cdb.companies.find({"symbol": name})
	for document in cursor:
		print document
	return

def test ():
	ddb.dictionary
	post = { 
		"word": dictword[0],
		"seen": dictword[1],
		"positive": dictword[2],
		"negative": dictword[3],
		}
	ddb.dictionary.insert_one(post)

def mainmenu ():
	while True:
#		try:
		option = input( "Options:\n1: Recreate Database\n2: List feed urls\n3: reset dictionary\n4: Let the sentiment analyzer train itself\n5: Train sentiment analyzer\n6: Get info on a company\n7: Show sentiments\n8: Show current dictionary\n9: Update all the companies data\n10: Exit\n")
		if option == 1:
			deldb()
		elif option == 2:
			listfeeds()
		elif option == 3:
			resetdictionary()
		elif option == 4:
			autotrain()
		elif option == 5:
			trainer()
		elif option == 6:
			name = raw_input("Enter Company ticker: ")
			printcompanyinfo(name)
		elif option == 7:
			listsentiments()
		elif option == 8:
			printdictionary()
		elif option == 9:
			batchcompanyupdate()
		elif option == 10:
			return
#		except:
#			print "error"
	return

#initsystem()
mainmenu()

