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
from multiprocessing import Pool

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
			"sentiment": getsentiment(entry.summary)}
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
			print getsentiment(entry.summary)
	return

def getsentiment (statement):
	sentimentdictionary = open('sentimentdictionary', 'r')
	lines = sentimentdictionary.readlines()
	dictwords = []
	for line in lines:
		dictword = line.split(',')
		dictwords.append(dictword)
	words = statement.split()
	p = 1
	n = 1
	sentiments = ['p', 'n', 'a']
	for word in words:
		for dictword in dictwords:
			if word == dictword[0]:
				if dictword[1].rstrip('\n') == sentiments[0]:
					p+=1
				elif dictword[1].rstrip('\n') == sentiments[1]:
					n+=1
				break
#	print "P: " + str(p) + "\tN: " + str(n)
	x = float(p)/n
	return x		

def listsentiments ():
	cursor = rdb.posts.find({"sentiment": {"$gt": 0}},{"_id": 0, "title": 1, "sentiment": 1}).sort("sentiment", pymongo.DESCENDING)
	for document in cursor:
		print document
	return

def trainer (RSSfeeds):
	sentimentdictionary = open('sentimentdictionary', 'r')
	lines = sentimentdictionary.readlines()
	dictwords = []
	sentiments = ['p', 'n', 'a']
	exitkeys = ['e']
	done = False
	for line in lines:
		temp = line.split(',')
		dictwords.append(temp)
	print "ready\n"
	for feed in RSSfeeds:
		print feed.url
		for entry in feed.entries:
			words = entry.summary.lower().split()
			for word in words:
				word = word.strip(string.punctuation)
				exists = False
				for dictword in dictwords:
					if word == dictword[0]:
						exists = True
				if exists == False:
					try :
						sentiment = raw_input("\"" + word + "\"\n")
					except:
						sentiment = 'q'
					if sentiment in sentiments:
						dictwords.append([word, sentiment])
						newdictentry= word + "," + sentiment + "\n"
						print newdictentry
						lines.append(newdictentry)
					elif sentiment in exitkeys:
						done = True
					if done == True: break
				if done == True: break
			if done == True: break
		if done == True: break
	sentimentdictionary.close()
	sentimentdictionary = open('sentimentdictionary', 'w')
	for line in lines:
		print>>sentimentdictionary, line.rstrip('\n')
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

def getrating(company):
	feed = feedparser.parse("http://finance.yahoo.com/rss/headline?s="+company[1])
	temp = []
	rating = 0
	for entry in feed.entries:
#		print "\"" + entry.summary + "\"\n"
		rating = rating + getsentiment(entry.summary);
	if (len(feed) != 0):
		rating = rating/len(feed)
	return rating

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
	companies = getcompanies(companies)
	
	pool.imap_unordered(companyupdate, companies)
	
	gettime = time.time() - gettime
	print "Total time to complete: " + str(gettime)

def getcompanies(companies):
	tempdir = r'./temp' 
	if not os.path.exists(tempdir):
		os.makedirs(tempdir)
	NASDAQlistings = open('nasdaq', 'r')
	lines = NASDAQlistings.readlines()
	for line in lines:
		urllib.urlretrieve (line, "./temp/temp.csv")
		with open("./temp/temp.csv", 'r') as doc:
			reader = csv.reader(doc)
			reader. next()	#skip first line
			for row in reader:
				company = []
				company.append(row[1])
				company.append(row[0])
				company.append(row[7])
				company.append(row[8])
				companies.append(company)
	return companies

def printcompanyinfo(name):
	cursor = cdb.companies.find({"company": name})
	for document in cursor:
		print document
	return

def mainmenu ():
	batchcompanyupdate()
	while True:
#		try:
		option = input( "Options:\n1: Create a database and save stuff\n2: List feed urls\n3: Add feed to list\n4: Remove feed from list\n5: Print feeds\n6: Train sentiment analyzer\n7: Get info on a company\n8: Show sentiments\n9: Delete database\n10: Exit\n")
		if option == 1:
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
			printfeeds(refreshfeeds())
		elif option == 6:
			trainer(refreshfeeds())
		elif option == 7:
			name = raw_input("Enter Company name: ")
			printcompanyinfo(name)
		elif option == 8:
			listsentiments()
		elif option == 9:
			deldb()
		elif option == 10:
			return
#		except:
#			print "error"
	return

#initsystem()
mainmenu()

