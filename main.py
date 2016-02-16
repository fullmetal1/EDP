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
from multiprocessing import Pool, Manager
from string import punctuation
from shutil import copyfile


try:
	client = pymongo.MongoClient()
	rdb = client.RSSdb
	rdb.createCollection( "RSSdb", { capped: true, max: 100 } )
except:
	print "RSS database already exists"
try:
	cdb = client.Companydb
	cdb.createCollection( "Companydb", { } )
except:
	print "Company database already exists"
try:
	ddb = client.Dictdb
	ddb.createCollection( "Dictionarydb", { } )
except:
	print "Dictionary database already exists"

def initsystem ():
	client = pymongo.MongoClient()
	rdb = client.RSSdb

	while True:
		insertentries(refreshfeeds())
		print "\n\nWaiting 15 minutes"
		time.sleep(15*60)
	return


def initdb ():
	try:
		insertentries(refreshfeeds())
	except:
		print "It's fucked Jim"
	return

def insertentries (RSSfeeds):
	for feed in RSSfeeds:
		for entry in feed.entries:
			post = { 
			"source": feed.url,
			"title": entry.title,
			"author": entry.author,
			"text": entry.summary,
			"url": entry.link,
			"date": entry.published,
			"date stored": time.time(),
			"sentiment": getsentiment(entry.summary, "sentimentdictionary")}
			if rdb.posts.find({"title": entry.title}).count() == 0:
				rdb.posts.insert_one(post)
				print "\"" + entry.title + "\" added"
			else:
				print "\"" + entry.title + "\" already exists"
	return

def refreshfeeds ():
	RSSURLfile = open('RSSfeeds', 'r+')
	RSSURLs = RSSURLfile.readlines()

	RSSfeeds =[]
	for RSSURL in RSSURLs:
		RSSfeeds.append(feedparser.parse(RSSURL))
	return RSSfeeds
	
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
			print getsentiment(entry.summary, "sentimentdictionary")
	return

def getsentiment (statement, dictionary):
	sentimentdictionary = open(dictionary, 'r')
	lines = sentimentdictionary.readlines()
	sentimentdictionary.close()
	dictwords = []
	for line in lines:
		dictword = line.split(',')
		dictwords.append(dictword)
	words = ''.join(c for c in statement if c not in punctuation).lower().split()
	numwords = 0
	x = 0
	for word in words:
		for dictword in dictwords:
			if word.encode('utf-8','ignore') == dictword[0]:
				numwords += 1
				x += float(int(dictword[2])-int(dictword[3]))/int(dictword[1])
				break
	if numwords != 0:
		x /= numwords	
	return x		

def listsentiments ():
	cursor = rdb.posts.find({"sentiment": {"$gt": 0}},{"_id": 0, "title": 1, "sentiment": 1}).sort("sentiment", pymongo.DESCENDING)
	for document in cursor:
		print document
	return

def autotrain ():
	gettime = time.time()
	companies = getcompanies()

	pool = Pool(processes=50)
	pool.imap_unordered(autotrainer, companies)
	gettime = time.time() - gettime
	print "Total time to complete: " + str(gettime)

def autotrainer (company):
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
		if getsentiment(statement, "autosentimentdictionary") >= 0.4:
			sentiment = 'p'
		elif getsentiment(statement, "autosentimentdictionary") > -0.4:
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
				dictword = json.load(db.dictionary.findone({"word": word.encode('utf-8','ignore')}))
				if sentiment == 'p':
					ddb.dictionary.update_one({"word": word}, {"$set": {"seen": dictword.seen+1, "positive": dictword.positive+1, "negative": dictword.negative}})
				elif sentiment == 'n':
					ddb.dictionary.update_one({"word": word}, {"$set": {"seen": dictword.seen+1, "positive": dictword.positive, "negative": dictword.negative+1}})
				else:
					ddb.dictionary.update_one({"word": word}, {"$set": {"seen": dictword.seen+1, "positive": dictword.positive, "negative": dictword.negative}})
			
		

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
			result = cdb.companies.update_one({"word": dictword[0]}, {"$set": {"seen": dictword[1], "positive": dictword[2], "negative": dictword[3]}})
		print>>sentimentdictionary, dictword[0]+","+str(dictword[1])+","+str(dictword[2])+","+str(dictword[3])
	sentimentdictionary.close()
	return

def addfeed (feed):
	RSSURLfile = open('RSSfeeds', 'r+')
	RSSURLs = RSSURLfile.readlines()
	RSSURLfile.close()
	feed = feed + '\n'
	RSSURLs.append(feed)

	RSSURLs = list(set(RSSURLs))
	RSSURLfile = open('RSSfeeds', 'w')
	for URL in RSSURLs:
		print>>RSSURLfile, URL.rstrip('\n')
	return
  	
def remfeed (feed):
	RSSURLfile = open('RSSfeeds', 'r+')
	RSSURLs = RSSURLfile.readlines()
	RSSURLfile.close()
	feed = feed + '\n'
	RSSURLs.remove(feed)

	RSSURLs = list(set(RSSURLs))
	RSSURLfile = open('RSSfeeds', 'w')
	for URL in RSSURLs:
		print>>RSSURLfile, URL.rstrip('\n')
	return

def listfeeds ():
	RSSURLfile = open('RSSfeeds', 'r+')
	RSSURLs = RSSURLfile.readlines()
	RSSURLs = list(set(RSSURLs))
	for RSSURL in RSSURLs:
		print RSSURL.rstrip('\n')
	return	

def deldb ():
	client.drop_database('RSSdb')
	client.drop_database('Companydb')
	return

def getrating (company):
	feed = feedparser.parse("http://finance.yahoo.com/rss/headline?s="+company[1])
	temp = []
	rating = 0
	for entry in feed.entries:
#		print "\"" + entry.summary + "\"\n"
		rating = rating + getsentiment(entry.summary, "sentimentdictionary");
	if (len(feed) != 0):
		rating = rating/len(feed)
	rating = rating + getstockrating(company)
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
	return float(opn)-float(clse)/float(clse);

def getstockrating(company):
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
		

def companyupdate(company):
	client = pymongo.MongoClient()
	cdb = client.Companydb

	if cdb.companies.find({"company": company[0]}).count() == 0:
		rating = getrating(company)
		post = { 
		"company": company[0],
		"symbol": company[1],
		"sector": company[2],
		"industry": company[3],
		"rating": rating,
		"updated": time.time()
		}
		cdb.companies.insert_one(post)
#		print "\"" + company[0] + "\" added. rating = " + str(rating)
	else:
		rating = getrating(company)
		result = cdb.companies.update_one({"company": company}, {"$set": {"rating": rating, "updated": time.time()}})
#		print "\"" + company[0] + "\" already exists. New rating = " + str(rating)

def batchcompanyupdate():
	gettime = time.time()
	pool = Pool(processes=50)
	companies = []
	companies = getcompanies()
	
	pool.imap_unordered(companyupdate, companies)
	
	gettime = time.time() - gettime
	print "Total time to complete: " + str(gettime)

def getcompanies():
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

def printcompanyinfo(name):
	cursor = cdb.companies.find({"company": name})
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
	batchcompanyupdate()
	while True:
#		try:
		option = input( "Options:\n1: Recreate Database\n2: List feed urls\n3: Add feed to list\n4: Remove feed from list\n5: Let the sentiment analyzer train itself\n6: Train sentiment analyzer\n7: Get info on a company\n8: Show sentiments\n9: Test yahoo financial data\n10: Exit\n")
		if option == 1:
			deldb()
			initdb()
		elif option == 2:
			listfeeds()
		elif option == 3:
			link = raw_input("Enter URL: ")
			addfeed(link)
		elif option == 4:
			link = raw_input("Enter URL: ")
			remfeed(link)
		elif option == 5:
			autotrain()
		elif option == 6:
			trainer()
		elif option == 7:
			name = raw_input("Enter Company name: ")
			printcompanyinfo(name)
		elif option == 8:
			listsentiments()
		elif option == 9:
			getstockrating(["Apple Inc", "AAPL"])
		elif option == 10:
			return
#		except:
#			print "error"
	return

#initsystem()
mainmenu()

