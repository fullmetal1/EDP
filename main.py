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
import mechanize
import datetime
from datetime import date, timedelta
from stem import Signal
from stem.control import Controller
import socks
import socket
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
from jdcal import gcal2jd, jd2gcal
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
	articles = getarticles(company[1])
	for article in articles:
		print article + "\n" + str(getsentiment(article))

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
		articles = getarticles(company[1])
		for article in articles:
			print article + "\n" + str(getsentiment(article))
		
def autotrainer (company):
	client = pymongo.MongoClient()
	ddb = client.Dictdb

	articles = getarticles(company[1])
	for article in articles:
		articlesentiment = getsentiment(article)
		if articlesentiment >= 1.0/3:
			sentiment = 'p'
		elif articlesentiment > -1.0/3:
			sentiment = 'a'
		else:
			sentiment = 'n'
		for word in article.split():
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
		articles = getarticles(company[1])
		for article in articles:
			sentiment = raw_input("\"" + article.encode("utf8","ignore") + "\"\n")
			if sentiment == 'e':
				break
			for word in article.split():

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
	words = getwordsfordate(ticker, date.today().strftime('%Y-%m-%d'))
	fst=''
	stop_words = set(stopwords.words("english"))
	filtered_words = [w for w in words if not w in stop_words]
	return filtered_words

def deldb ():
	client.drop_database('Companydb')
	client.drop_database('Dictdb')
	return

def getrating (ticker):
	words = getwordsfordate(ticker, date.today().strftime('%Y-%m-%d'))
	rating = 0
	length = len(words)
	imprtntwrds = importantwords(ticker)
	rating += getimportantsentiment(" ".join(words),imprtntwrds);
	if (length != 0):
		rating = rating/length
	return rating

def getstockchange (ticker):
	yesterday = (date.today() - timedelta(1)).strftime('%Y-%m-%d')
	try:
		opn = Share(ticker).get_historical(yesterday, yesterday)[0][u'Open']
		cls = Share(ticker).get_historical(yesterday, yesterday)[0][u'Close']
		print opn
		print cls
	except:
		return 0
	return (float(clse)-float(opn))/float(opn);

def companyupdate (company):
	client2 = pymongo.MongoClient(connect=False)
	cdb = client2.Companydb
	ddb = client2.Dictdb

	if cdb.companies.find({"company": company[0]}).count() == 0:
		rating = getrating(company[1])
		post = { 
		"company": company[0],
		"symbol": company[1],
		"sector": company[2],
		"industry": company[3],
		"rating": rating,
		"updated": time.time(),
		}
		cdb.companies.insert_one(post)
		print "\"" + company[0] + "\" added. rating = " + str(rating)
	else:
		rating = getrating(company[1])
		result = cdb.companies.update_one({"company": company}, {"$set": {"rating": rating, "updated": time.time()}})
		print "\"" + company[0] + "\" already exists. New rating = " + str(rating)
	client2.close()

def batchcompanyupdate ():
	gettime = time.time()
	pool = Pool(processes=50)
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

def gettext (ticker, js):
	browser = mechanize.Browser()
	browser.set_handle_robots(False)
	browser.addheaders= [('User-agent','Chrome')]
	return browser.open("https://www.googleapis.com/customsearch/v1element?key=AIzaSyCVAXiUzRYsML1Pv6RwSG1gunmMikTzQqY&rsz=filtered_cse&num=10&hl=en&prettyPrint=false&source=gcsc&gss=.com&sig=432dd570d1a386253361f581254f9ca1&cx=004415538554621685521:vgwa9iznfuo&q=stocks:"+ticker+"%20daterange%3A"+js+"%2D"+js+"&googlehost=www.google.com&callback=google.search.Search.apiary9284&nocache=1459649736099").read()
	
def getarticlesfordate(ticker, day):
	day=day.split('-')
	year=day[0]
	month=day[1]
	day=day[2]
	jday1= gcal2jd(year,month,day)
	jday1= jday1[0]+jday1[1]+0.5
	jday1= int(jday1)
	js=str(jday1)

	temp = socket.socket
	socket.socket = socks.socksocket
	txt = gettext(ticker, js)
	socket.socket = temp
	txt = txt[48:]
	l= len(txt)
	txt = txt[:l-2]
	articles = []
	for result in json.loads(txt)[u'results']:
		article = []
		article.append(result[u'titleNoFormatting'])
		article.append(result[u'contentNoFormatting'])
		articles.append(article)
	return articles

def getwordsfordate(ticker, day):
	day=day.split('-')
	year=day[0]
	month=day[1]
	day=day[2]
	jday1= gcal2jd(year,month,day)
	jday1= jday1[0]+jday1[1]+0.5
	jday1= int(jday1)
	js=str(jday1)

	temp = socket.socket
	socket.socket = socks.socksocket
	txt = gettext(ticker, js)
	socket.socket = temp
	txt = txt[48:]
	l= len(txt)
	txt = txt[:l-2]
	words = ""
	for result in json.loads(txt)[u'results']:
		words += result[u'contentNoFormatting'] + " " + result[u'titleNoFormatting']
	words =''.join(c for c in words if c not in punctuation+'-').lower()
	return words.rstrip('\n').split()

def getarticles(ticker):
	day=date.today().strftime('%Y-%m-%d').split('-')
	year=day[0]
	month=day[1]
	day=day[2]
	jday1= gcal2jd(year,month,day)
	jday1= jday1[0]+jday1[1]+0.5
	jday1= int(jday1)
	js=str(jday1)

	temp = socket.socket
	socket.socket = socks.socksocket
	txt = gettext(ticker, js)
	socket.socket = temp
	txt = txt[48:]
	l= len(txt)
	txt = txt[:l-2]
	articles = []
	for result in json.loads(txt)[u'results']:
		article = result[u'contentNoFormatting'] + " " + result[u'titleNoFormatting']
		article = ''.join(c.rstrip('\n') for c in article if c not in punctuation+'-').lower()
		articles.append(article)
	return articles

def getclosingpricefordate(ticker, day):
	try:
		close = Share(ticker).get_historical(day, day)[0][u'Close']
	except:
		close = 0
	return close

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

with Controller.from_port(port = 9051) as controller:
	controller.authenticate()
	socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, "127.0.0.1", 9050)
#	socket.socket = socks.socksocket

#initsystem()

mainmenu()

#for company in getcompanies():
#	companyupdate (company)

