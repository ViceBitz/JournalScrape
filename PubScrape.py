from bs4 import BeautifulSoup
import requests
from selenium import webdriver
import time
import math
headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:102.0) Gecko/20100101 Firefox/102.0',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'en-US,en;q=0.5',
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
}

"""
Extracts all section pages and article links from a specified publication. Retrieves relevant
information (publishing date / headline / subhead / body text). Extracts links from buttons in front page
to find section names, then uses the fact that links to full section articles for SNO sites
are <publication link>/category/<section name>

@author Victor Gong
@version 7/27/2024
"""

#Relevant sections for the purpose of political analysis
relevantSectionTags = [("news","news"), ("op","opinion"), ("feat","feature"),
                       ("news", "events"), ("op","humor"), ("feat","feat"),
                       ("op","op-ed"), ("feat","showcase"), ("op","politic"),
							  ("op","editorial")] #News, opinions, features

#Checks if a given publication is accessible by 'requests' module (extension of urlExists)
def pubScrapable(pubLink):
	exists = urlExists(pubLink)
	if urlExists:
		print(pubLink + " exists"); return True
	else: return False

#Checks if a page/URL exists
def urlExists(url):
	url = url.replace("http://","https://")
	try:
		check = requests.head(url, headers=headers); requests.get(url, headers=headers)
		return check.status_code >= 200 and check.status_code < 400
	except Exception as e:
		return False
	
#Gets all valid section page URLs of a specific publication (if 404 Error, skips)
#Returns table of URLs in the format [(sectionName, url),...]
def getValidSectionURLs(pubLink):
	if pubLink[len(pubLink)-1] == "/": pubLink = pubLink[:len(pubLink)-1] #Get rid of ending "/"

	frontPageHTML = requests.get(pubLink+"/?full-site", headers=headers).content
	soup = BeautifulSoup(frontPageHTML, features="html.parser")

	sectionURLs = []
	usedSections = set()

	#Scrape buttons on front page (filter by parent and text) -> first pass
	allButtons = soup.find_all("a")

	priorityLinks = []
	for urlEle in allButtons:
		if (urlEle != None and urlEle.has_attr("href") and urlEle.parent != None
			and urlEle.parent.has_attr("class") and len(urlEle.parent["class"]) >= 3 and "menu-item-type" in urlEle.parent["class"][1]):
				url = urlEle["href"]
				text = urlEle.text
				if not ("http://" in url or "https://" in url): continue
				if url in priorityLinks: continue
				for _,tag in relevantSectionTags:
					if tag in text.lower():
						priorityLinks.append(url); break
	priorityLinks = sorted(priorityLinks, key=lambda x: len(x)) #Sort by string length

	#Match with each relevant tag
	for section, tag in relevantSectionTags:
		if section in usedSections: continue #No repeats
		if len(usedSections) == 3: break #Break if sections already found

		for url in priorityLinks:
			#Process link
			if "https://" in url: urlRaw = url.replace("https://","")
			else: urlRaw = url.replace("http://","")
			if urlRaw[len(urlRaw)-1] == "/": urlRaw = urlRaw[:len(urlRaw)-1]
			urlRaw = urlRaw.split("/")

			#Check which relevant section it aligns with
			keyWord = urlRaw[len(urlRaw)-1] if len(urlRaw)>=2 else None #Has to be at least 2 directories long
			if keyWord != None:
				possibleLink = pubLink + "/category/" + keyWord
				if tag in keyWord:
					if urlExists(possibleLink):
						sectionURLs.append((section, possibleLink)); usedSections.add(section); break
					elif urlExists(url):
						sectionURLs.append((section, url)); usedSections.add(section); break #If possibleLink doesn't work, default to url

	#Second pass, include rest of links				
	allLinks = []
	for urlEle in allButtons: #Second pass, all
		if (urlEle != None and urlEle.has_attr("href")):
				url = urlEle["href"]
				text = urlEle.text
				if not ("http://" in url or "https://" in url): continue
				if url in allLinks or url in priorityLinks: continue
				for _,tag in relevantSectionTags:
					if tag in text.lower():
						allLinks.append(url); break
	allLinks = sorted(allLinks, key=lambda x: len(x)) #Sort by string length

	#Match with each relevant tag
	for section, tag in relevantSectionTags:
		if section in usedSections: continue #No repeats
		if len(usedSections) == 3: break #Break if sections already found

		for url in allLinks:
			#Process link
			if "https://" in url: urlRaw = url.replace("https://","")
			else: urlRaw = url.replace("http://","")
			if urlRaw[len(urlRaw)-1] == "/": urlRaw = urlRaw[:len(urlRaw)-1]
			urlRaw = urlRaw.split("/")

			#Check which relevant section it aligns with
			keyWord = urlRaw[len(urlRaw)-1] if len(urlRaw)>=2 else None #Has to be at least 2 directories long
			if keyWord != None:
				possibleLink = pubLink + "/category/" + keyWord
				if tag in keyWord:
					if urlExists(possibleLink):
						sectionURLs.append((section, possibleLink)); usedSections.add(section); break
					elif urlExists(url):
						sectionURLs.append((section, url)); usedSections.add(section); break #If possibleLink doesn't work, default to url
	
				
	print(pubLink, sectionURLs)
	return sectionURLs


#Scrapes all article links off a designated section page
def scrapeArticlesOffSectionPage(sectionURL, maxPages):
	#Get article pages one by one with sectionURL/pages/#/
	articleLinks = []; articleSet = set() #Helps check for duplicates
	pageNum = 1; pageURL = sectionURL+"/page/"+str(pageNum)
	while (pageNum <= maxPages and urlExists(pageURL)):
		pageHTML = requests.get(pageURL).content; print("On",pageNum,"|",pageURL)
		soup = BeautifulSoup(pageHTML, features="html.parser")

		#Extract article links from element <a href=...> on the page
		articles = soup.find_all("a", {"class":"homeheadline", "title":"Permanent Link to Story"})
		if len(articles) == 0: articles = soup.find_all("a", {"class":"homeheadline"}) #Widen search if no articles
		for a in articles:
			if a.has_attr("href"):
				link = a["href"]
				if not link in articleSet:
					articleLinks.append(link); articleSet.add(link)

		pageNum+=1; pageURL = sectionURL+"/page/"+str(pageNum)

	#driver.quit()
	return articleLinks

#Scrapes all articles from a given high school publication, going through each relevant section
#Returns table of articles from each section in the format [[sectionName, links...],...]
def scrapeAllArticles(pubLink, pubName, maxPerSection):
	allArticles = []
	totalArticleCount = 0
	for section, url in getValidSectionURLs(pubLink):

		sectionArticles = [section]
		articleCount = 0
		for u in scrapeArticlesOffSectionPage(url, int(math.ceil(maxPerSection/8))): #Estimate ~8 articles per subpage
			sectionArticles.append(u)
			articleCount+=1
			if articleCount >= maxPerSection: #Cut off at 'maxPerSection' articles
				break
		if articleCount > 0: allArticles.append(sectionArticles)
		totalArticleCount += articleCount
	print("Article scrape stats for",pubLink,":\n==========================================================\n-",
		 len(allArticles),"sections\n-",
		 totalArticleCount,"articles\n==========================================================")
	return pubName, allArticles