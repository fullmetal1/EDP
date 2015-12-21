import sys
import feedparser
import json
import pymongo
import subprocess
import time
import string

def initsystem ():
	client = pymongo.MongoClient()
	db = client.RSSdb

	while True:
		insertentries(refreshfeeds())
		print "\n\nWaiting 15 minutes"
		time.sleep(15*60)
	return

def initdb():
	try:
		client = pymongo.MongoClient()
		db = client.RSSdb
		db.createCollection( "RSSdb", { capped: true, max: 100 } )
	except:
		print "database already exists"
	try:
		insertentries(refreshfeeds())
	except:
		print "It's fucked Jim"
#	print "HELLO WORLD"
#	insertentries(refreshfeeds())
	return

def insertentries (RSSfeeds):
	client = pymongo.MongoClient()
	db = client.RSSdb	

	for feed in RSSfeeds:
		for entry in feed.entries:
			post = { 
			"source": feed.url,
			"title": entry.title,
			"author": entry.author,
			"text": entry.summary,
			"url": entry.link,
			"date": entry.published,
			"date stored": time.time()}
			if db.posts.find({"title": entry.title}).count() == 0:
				db.posts.insert_one(post)
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
			print entry.title
	return

def getsentiment(statement):
	sentimentdictionary = open('sentimentdictionary', 'r')
	lines = sentimentdictionary.readlines()
	dictwords = []
	for line in lines:
		dictword = line.split(',')
		dictwords.append(dictword)
	words = statement.split()
	p = 0
	n = 0
	sentiments = ['p', 'n', 'a']
	for word in words:
		for dictword in dictwords:
			if word == dictword[0]:
				if dictword[1].rstrip('\n') == sentiments[0]:
					p+=1
				elif dictword[1].rstrip('\n') == sentiments[1]:
					n+=1
				break
	print "P: " + str(p) + "\tN: " + str(n)
	if p > n:
		return	"positive"
	elif n > p:
		return "negative"
	return "neutral"		

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

def mainmenu ():
	while True:
#		try:
		option = input( "Options:\n1: Create a database and save stuff\n2: list feed urls\n3: add feed to list\n4: remove feed from list\n5: print feeds\n6: train sentiment analyzer\n7: analyze sentiments\n8: exit\n")
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
			feeds = refreshfeeds()
			for feed in feeds:
				for entry in feed.entries:
					print "\"" + entry.summary + "\"" + " " + getsentiment(entry.summary)
		elif option == 8:
			return
#		except:
#			print "error"
	return

#initsystem()
mainmenu()
