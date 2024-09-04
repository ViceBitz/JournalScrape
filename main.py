"""
JournoScrape Main Driver

@author Victor Gong
@version 7/27/2024
"""

import csv
import SNOScrape, PubScrape, ArticleScrape
from concurrent.futures import ThreadPoolExecutor
import Visualizer
import Analyzer
import AutoPrinter as AP
import itertools

#INSTALL ALL LIBRARIES IN TERMINAL/COMMAND PROMPT WITH: pip install -r /path/to/requirements.txt

#Data files
pubsFileName = "data/publications_test.csv" #Journalism publications to process (name, state, city, link)
pubsReferenceFileName = "data/publications_abridged.csv" #All publications with info (for creating dicts)
urlsFileName = "data/article_urls.csv" #Article URLs from specific sections in every publication
infoFileName = "data/article_info.csv" #Headline, date, and body text of all articles
storageFileName = "data/article_storage.csv" #Temporary storage for articles, e.g. used during categorical sorting

#Result files
catStatsFileName = "results/category_stats.csv" #Topic categories of articles with frequency and average political lean
pubPoliticsFileName = "results/pub_politics.csv" #Calculated publication political rating
cityPoliticsFileName = "results/city_politics.csv" #Calculated city political rating
statePoliticsFileName = "results/state_politics.csv" #Political ratings in the format [state, (pubName, pubRating), ...]
zonePoliticsFileName = "results/zone_politics.csv" #Political ratings by county in two groups, blue vs. red with general voter data
fullPoliticsFileName = "results/full_politics.csv" #Political ratings of all publications and their counties

#Dictionaries
pubDict = {} #Format: {schoolName -> (pubState, pubCity, pubLink)}
articleDict = {} #Format: {articleURL -> (headline, bodyText)}
articleRatingDict = {} #Format: {articleURL -> rating}
cityPubDict = {} #Format: {state -> {city -> [(school name, rating),...]}}
countyPubDict = {} #Format: {state -> {county -> [(school name, rating)]}}
catDict = {} #Format: {topic -> [frequency, political lean]}


"""
=========================================================
                     DATA SCRAPING
=========================================================
"""
#Scrapes and writes all publication info to data file (pubsFileName)
def getPublicationData():
   publications = SNOScrape.scrapePublicationURLs()
   AP.printLine(); print("Scrape Publication Info (from SNO network)"); AP.printLine()
   
   with open(pubsFileName, "w") as csvF:
      csvWriter = csv.writer(csvF)
      csvWriter.writerow(["Name", "State/Country", "City", "Link"])
      
      #Write all publication info into file
      for name, state, city, link in publications:
         csvWriter.writerow([name, state, city, link])

#Abridges publication list (by cutFactor) with jump selection (e.g. cutFactor = 5, skip 4, write 1)
#More importantly, removes schools with invalid addresses (doesn't exist / not in U.S.) or duplicates
         
def checkPubValid(pubInfo):
   if Visualizer.getLatLong(pubInfo[2], pubInfo[1]) != None and PubScrape.pubScrapable(pubInfo[3]):
      return pubInfo
   return None

def abridgePublicationData(abridgedFileName, cutFactor, cutSeed):
   abridgedList = []
   schoolNames = set()
   threadWorkers = 500 #Number of threads for abridging

   #Read from publication file
   with open(pubsFileName, "r") as csvF:
      csvReader = csv.reader(csvF)
      csvContent = [line for line in csvReader]

      print("Abridging publication list of",len(csvContent[1:]),"schools...")
      
      #Check publication validity
      with ThreadPoolExecutor(max_workers=threadWorkers) as executor:
         results = executor.map(checkPubValid, csvContent[1:])
      validResults = []
      for r in results:
         if r != None: validResults.append(r)

      print("Making jump selection cut...")
      #Make jump selection cut
      m = 0
      for pubInfo in validResults:        
         if (m+cutSeed)%cutFactor==0 and not pubInfo[0] in schoolNames:
            abridgedList.append((pubInfo[0], pubInfo[1], pubInfo[2], pubInfo[3]))
            schoolNames.add(pubInfo[0].lower())
         m+=1
   
   print("Writing to abridged file " + abridgedFileName)
   #Write to abridged file
   with open(abridgedFileName, "w") as csvF:
      csvWriter = csv.writer(csvF)
      csvWriter.writerow(["Name", "State/Country", "City", "Link"])
      
      #Write all publication info into file
      for name, state, city, link in abridgedList:
         csvWriter.writerow([name, state, city, link])
   
   print(len(csvContent[1:]), "publications ->", len(abridgedList), "publications")
   
#Scrapes and writes all article URLs of every publication to data file (articlesFileName)
#Gets publication URLs from "publications.csv"
def getArticleURLs():
   urlTable = [] #Format [[[pubName, pubState, pubCity, pubURL], [sectionName, articleURL...]]...]
   threadWorkers = 15 #Number of threads to open for processing

   AP.printLine(); print("Scrape Article URLs"); AP.printLine()
   
   #Read from publication URLs and scrape
   with open(pubsFileName, "r") as csvF:
      csvReader = csv.reader(csvF)
      csvContent = [line for line in csvReader]

      allLinks = []; allNames = []; pageScrapeResults = []
      for pubInfo in csvContent[1:]:
         pubName = pubInfo[0]; pubLink = pubInfo[3]
         allLinks.append(pubLink); allNames.append(pubName)

      for t in range(0,len(allLinks),threadWorkers): #Process 'threadWorkers' amount at a time
         with ThreadPoolExecutor(max_workers=threadWorkers) as executor: #Scrape articles with multithreading
            tEnd = min(t+threadWorkers, len(allLinks))
            results = list(executor.map(PubScrape.scrapeAllArticles, allLinks[t:tEnd], allNames[t:tEnd], itertools.repeat(30)))
            for r in results: pageScrapeResults.append(r)

      for pubName, articles in pageScrapeResults:
         articleTable = [pubName]
         for sectionArticles in articles:
            articleTable.append(sectionArticles)
      
         urlTable.append(articleTable)

   #Write to article URL file
   with open(urlsFileName, "w") as csvF:
      csvWriter = csv.writer(csvF)
      csvWriter.writerow([len(urlTable)]) #Write # of publications

      for articleTable in urlTable:
         csvWriter.writerow([articleTable[0]]) #Write school name
         csvWriter.writerow([len(articleTable[1:])]) #Write # of sections

         for sectionTable in articleTable[1:]:
            csvWriter.writerow([sectionTable[0]]) #Write section name
            csvWriter.writerow(sectionTable[1:]) #Write article URLs

#Scrapes article info (headline, body text) from every publication and writes to data file (infoFileName)
def getArticleInfo():
   infoTable = [] #Format [[pubName, [sectionName, [articleURL, headline, date, body], ...], ...], ...]
   AP.printLine(); print("Scrape Article Info"); AP.printLine()

   #Read articles from articles.csv and scrape
   with open(urlsFileName, "r") as csvF:
      csvReader = csv.reader(csvF)
      csvContent = [line for line in csvReader]

      pubCount = int(csvContent[0][0]); print(pubCount,"publications\n")

      it = 1
      for _ in range(pubCount):
         pubName = csvContent[it][0]; it+=1; print(pubName)
         sectionCount = int(csvContent[it][0]); it+=1; print("-",sectionCount, "sections-\n")
         articleCount = 0
         
         pubData = [pubName]
         for _ in range(sectionCount):
            sectionName = csvContent[it][0]; it+=1; print("-",pubName, "/", sectionName,"-")
            sectionArticleURLs = csvContent[it]; it+=1

            sectionData = [sectionName]

            with ThreadPoolExecutor(max_workers=len(sectionArticleURLs)) as executor: #Scrape articles with multithreading
               articleScrapeResults = list(executor.map(ArticleScrape.scrapeArticle, sectionArticleURLs))
            
            for articleURL, headline, date, bodyText in articleScrapeResults:
               if headline == None: continue #Skip outliers
               sectionData.append([articleURL, headline, date, bodyText]); print(headline, " | ", date)
               articleCount+=1

            pubData.append(sectionData)

         infoTable.append(pubData)
         print("Processed",articleCount,"article(s)"); AP.printLine()
   
   #Write results to info.csv
   with open(infoFileName, "w") as csvF:
      csvWriter = csv.writer(csvF)

      csvWriter.writerow([str(len(infoTable))]) #Write # of publications

      for pubData in infoTable:
         pubName = pubData[0]

         csvWriter.writerow([pubName])
         csvWriter.writerow([str(len(pubData[1:]))]) #Write # of sections

         for sectionData in pubData[1:]:
            sectionName = sectionData[0]

            csvWriter.writerow([sectionName])
            csvWriter.writerow([str(len(sectionData[1:]))]) #Write # of articles

            for articleData in sectionData[1:]:
               csvWriter.writerow(articleData) #Writes articleURL, headline, date, body text
               #print("Writing:", articleData[1], " | ", articleData[2])

#Weeds out all articles that are too short to consider and cuts valid articles down to character limit
def abridgeArticleInfo(outputFileName):
   infoTable = []
   totalArticleCount = 0

   #Read from article info file and cut
   with open(infoFileName, "r") as csvF:
      csvReader = csv.reader(csvF)
      csvContent = [line for line in csvReader]
      pubCount = int(csvContent[0][0])

      it = 1
      for _ in range(pubCount):
         pubName = csvContent[it][0]; it+=1
         sectionCount = int(csvContent[it][0]); it+=1
         
         pubData = [pubName]
         for _ in range(sectionCount):
            sectionName = csvContent[it][0]; it+=1
            articleCount = int(csvContent[it][0]); it+=1

            sectionData = [sectionName]
            for _ in range(articleCount):
               bodyText = csvContent[it][3]; totalArticleCount+=1
               if not Analyzer.articleTooShort(bodyText):
                  sectionData.append([csvContent[it][0],csvContent[it][1],csvContent[it][2],Analyzer.cutBodyText(bodyText)])
               it+=1

            pubData.append(sectionData)

         infoTable.append(pubData)
   
   #Write back results to output file
   finalArticleCount = 0
   with open(outputFileName, "w") as csvF:
      csvWriter = csv.writer(csvF)

      csvWriter.writerow([str(len(infoTable))]) #Write # of publications

      for pubData in infoTable:
         pubName = pubData[0]

         csvWriter.writerow([pubName])
         csvWriter.writerow([str(len(pubData[1:]))]) #Write # of sections

         for sectionData in pubData[1:]:
            sectionName = sectionData[0]

            csvWriter.writerow([sectionName])
            csvWriter.writerow([str(len(sectionData[1:]))]) #Write # of articles

            for articleData in sectionData[1:]:
               csvWriter.writerow(articleData) #Writes articleURL, headline, date, body text
               finalArticleCount+=1
   print(totalArticleCount,"articles -> ",finalArticleCount,"articles")

"""
=========================================================
                     DATA RETRIEVAL
=========================================================
"""

#Creates publication dictionary
def createPublicationInfoDict():
   #Read from publication reference file
   with open(pubsReferenceFileName, "r") as csvF:
      csvReader = csv.reader(csvF)
      csvContent = [line for line in csvReader]
      
      for pubInfo in csvContent[1:]:        
         pubDict[pubInfo[0]] = (pubInfo[1], pubInfo[2], pubInfo[3])

#Creates article info dictionary
def createArticleInfoDict():
   #Read article information
   global articleDict
   with open(infoFileName, "r") as csvF:
      csvReader = csv.reader(csvF)
      csvContent = [line for line in csvReader]

      pubCount = int(csvContent[0][0])
      it = 1
      for _ in range(pubCount):
         pubName = csvContent[it][0]; it+=1
         sectionCount = int(csvContent[it][0]); it+=1
         for _ in range(sectionCount):
            sectionName = csvContent[it][0]; it+=1
            articleCount = int(csvContent[it][0]); it+=1
            for _ in range(articleCount):
               url = csvContent[it][0]
               headline = csvContent[it][1]
               bodyText = csvContent[it][3]; it+=1
               articleDict[url] = (headline, bodyText)

#Creates article political rating dictionary
def createArticleRatingDict():
   #Read article ratings from article politics eval file
   with open(Analyzer.politicsEvalFileName, "r") as csvF:
      csvReader = csv.reader(csvF)
      csvContent = [line for line in csvReader]

      for articleInfo in csvContent:
         url = articleInfo[2]
         evalRating = articleInfo[3].split(" | ")[0]

         try: #Catch conversion errors just in case
            rating = float(evalRating)
         except Exception as e:
            rating = 0.0
         
         articleRatingDict[url] = rating
         

#Creates city politics dictionary
def createCityPoliticalDict():
   #Read publication ratings from publication politics file
   global cityPubDict
   with open(pubPoliticsFileName, "r") as csvF:
      csvReader = csv.reader(csvF)
      csvContent = [line for line in csvReader] 

      for pubInfo in csvContent:
         pubName = pubInfo[0]
         pubRating = float(pubInfo[1])
         state, city, url = pubDict[pubName]
         
         if not state in cityPubDict: cityPubDict[state] = {}
         if not city in cityPubDict[state]: cityPubDict[state][city] = []

         cityPubDict[state][city].append((pubName, pubRating))

#Creates county politics dictionary
def createCountyPoliticalDict():
   #Read publication ratings from publication politics file
   global countyPubDict
   with open(pubPoliticsFileName, "r") as csvF:
      csvReader = csv.reader(csvF)
      csvContent = [line for line in csvReader] 

      for pubInfo in csvContent:
         pubName = pubInfo[0]
         pubRating = float(pubInfo[1])
         state, city, url = pubDict[pubName]
         county = Visualizer.getCounty(city, state)

         if not county: continue
         if not state in countyPubDict: countyPubDict[state] = {}
         if not county in countyPubDict[state]: countyPubDict[state][county] = []

         countyPubDict[state][county].append((pubName, pubRating))

#Creates category dictionary by calculating frequency and political lean of each topic (also writes to file)
def createCategoryDict():
   #Read article ratings from article politics eval file
   with open(Analyzer.politicsCatFileName, "r") as csvF:
      csvReader = csv.reader(csvF)
      csvContent = [line for line in csvReader]

      for articleInfo in csvContent:
         articleURL = articleInfo[2]
         category = articleInfo[3]
         if category not in catDict: catDict[category] = [0, 0.0] #Frequency, political lean
         if articleURL not in articleRatingDict: continue
         catDict[category][0] += 1
         catDict[category][1] += articleRatingDict[articleURL]
   
   #Calculate average political lean by dividing sum by frequency
   for category in list(catDict.keys()):
      catDict[category][1] /= catDict[category][0]
      if catDict[category][0] < 20: del catDict[category] #Delete outlier categories

   #Write to category stats file
   with open(catStatsFileName, "w") as csvF:
      csvWriter = csv.writer(csvF)
      for category in list(catDict.keys()):
         csvWriter.writerow([category, catDict[category][0], catDict[category][1]]) #Write publication rating

"""
=========================================================
                     DATA ANALYSIS
=========================================================
**Note, 'send' methods append rather than overwrite to allow for several batches of processing
"""

#Analyzes articles politically from every publication and calculates a partisanship score (-42 to 42) (DEPRECATED)
"""
def analyzePublicationArticlePolitics():
   politicsTable = [] #Format [[pubName, [sectionName, (headline, rating, url), ...]...]...]...]
   totalArticleCount = 0
   AP.printLine(); print("Political Analysis"); AP.printLine()

   #Read article information
   with open(infoFileName, "r") as csvF:
      csvReader = csv.reader(csvF)
      csvContent = [line for line in csvReader]

      pubCount = int(csvContent[0][0])
      it = 1
      for _ in range(pubCount):
         pubName = csvContent[it][0]; it+=1; print(pubName)
         pubTable = [pubName]

         sectionCount = int(csvContent[it][0]); it+=1
         for _ in range(sectionCount):
            sectionName = csvContent[it][0]; it+=1; print(sectionName)
            sectionTable = [sectionName]

            articleCount = int(csvContent[it][0]); it+=1
            for _ in range(articleCount):
               url = csvContent[it][0]
               headline = csvContent[it][1]
               bodyText = csvContent[it][3]; it+=1
               rating, justification = Analyzer.politicsAnalyze(headline, bodyText) #Analyze this article politically

               sectionTable.append((headline, rating, justification, url))

               if justification != "Not political":
                  print(headline, "|", str(rating), "|", justification)
            
            pubTable.append(sectionTable)
            totalArticleCount += articleCount

         politicsTable.append(pubTable)
   
   AP.printLine(); print("Writing to", articlePoliticsFileName)
   #Write to article politics file
   with open(articlePoliticsFileName, "w") as csvF:
      csvWriter = csv.writer(csvF)

      csvWriter.writerow([len(politicsTable)]) #Write # of publications

      for pubTable in politicsTable:
         csvWriter.writerow([pubTable[0]]) #Write school name
         csvWriter.writerow([len(pubTable[1:])]) #Write # of sections

         for sectionTable in pubTable[1:]:
            csvWriter.writerow([sectionTable[0]]) #Write section name
            csvWriter.writerow([len(sectionTable[1:])]) #Write # of articles

            for headline, rating, justification, url in sectionTable[1:]:
               csvWriter.writerow([headline, rating, justification, url]) #Write article ratings
   
   print("Rated",totalArticleCount,"articles across",pubCount,"publications"); AP.printLine()
"""

#Sends a bulk request to Batch API for black-white political analysis of all articles
def sendRequest_ArticlesBWPolitics(startIndex=0, confirmMsg=True):
   AP.printLine(); print("Sending bulk request for BW analysis"); AP.printLine()

   #Read article information
   articleTable = []
   with open(infoFileName, "r") as csvF:
      csvReader = csv.reader(csvF)
      csvContent = [line for line in csvReader]

      pubCount = int(csvContent[0][0])
      it = 1
      for _ in range(pubCount):
         pubName = csvContent[it][0]; it+=1
         sectionCount = int(csvContent[it][0]); it+=1
         for _ in range(sectionCount):
            sectionName = csvContent[it][0]; it+=1
            articleCount = int(csvContent[it][0]); it+=1
            for _ in range(articleCount):
               url = csvContent[it][0]
               headline = csvContent[it][1]
               bodyText = csvContent[it][3]; it+=1
               articleTable.append((pubName, sectionName, url, headline, bodyText)) #Append to table
               
   print("Total article count:", len(articleTable))
   #Send the request through Analyzer module
   Analyzer.createBatch_BWAnalysis(articleTable, startIndex, confirmMsg)


#Sends a bulk request to Batch API for full political evaluation of white (politically-marked) articles
def sendRequest_ArticlesEvalPolitics(startIndex=0, fileLineStart=1, confirmMsg=True):
   totalArticleCount = 0
   
   AP.printLine(); print("Sending bulk request for political evaluation"); AP.printLine()

   #Read article information
   articleTable = []; articleSet = set()
   with open(Analyzer.politicsBWFileName, "r") as csvF:
      csvReader = csv.reader(csvF)
      csvContent = [line for line in csvReader]

      for articleInfo in csvContent[fileLineStart-1:]:
         pubName = articleInfo[0]
         sectionName = articleInfo[1]
         url = articleInfo[2]
         isPolitical = "y" in articleInfo[3].lower()
         headline, bodyText = articleDict[url]

         #Check if article related to politics (from BW analysis) and prevent repetitions
         if isPolitical and url not in articleSet:
            articleTable.append((pubName, sectionName, url, headline, bodyText)) #Append to table
            articleSet.add(url)

   print("Total article count:", len(articleTable))
   #Send the request through Analyzer module
   Analyzer.createBatch_PoliticalEval(articleTable, startIndex, confirmMsg)

#Sends a bulk request to Batch API for categorical topic sorting of white (politically-marked) articles
#*Because of the state-by-state method of scraping, data was lost in the process, so have to re-scrape all article URLs
def sendRequest_ArticlesCategoricalTopics(startIndex=0, fileLineStart=1, confirmMsg=True, readFromStorage=True):
   totalArticleCount = 0
   
   AP.printLine(); print("Sending bulk request for categorical sorting"); AP.printLine()

   articleTable = []; 
   if not readFromStorage:
      #Read article URLs
      articleURLs = []; URLDict = {}
      with open(Analyzer.politicsBWFileName, "r") as csvF:
         csvReader = csv.reader(csvF)
         csvContent = [line for line in csvReader]

         for articleInfo in csvContent[fileLineStart-1:]:
            pubName = articleInfo[0]
            sectionName = articleInfo[1]
            url = articleInfo[2]
            isPolitical = "y" in articleInfo[3].lower()
            if isPolitical and url not in articleURLs:
               articleURLs.append(url)
               URLDict[url] = (pubName, sectionName)

      #Scrape headline and body text from URLs
      stepSize = 100
      for index in range(0,len(articleURLs),stepSize):
         #Scrape articles with multithreading
         articleSplice = articleURLs[index:min(index+stepSize,len(articleURLs)-1)]
         with ThreadPoolExecutor(max_workers=len(articleSplice)) as executor:
            articleScrapeResults = list(executor.map(ArticleScrape.scrapeArticle, articleSplice))

         with open(storageFileName, "a") as csvF:
            csvWriter = csv.writer(csvF)
            for url, headline, date, bodyText in articleScrapeResults:
               if headline == None: continue #Skip outliers
               pubName, sectionName = URLDict[url]
               articleTable.append((pubName, sectionName, url, headline, bodyText)) #Append to table
               csvWriter.writerow([pubName, sectionName, url, headline, bodyText]) #Append to storage file
               print(headline, " | ", date)
   else:
      with open(storageFileName, "r") as csvF:
         csvReader = csv.reader(csvF)
         csvContent = [line for line in csvReader]
         for articleInfo in csvContent[fileLineStart-1:]:
            pubName = articleInfo[0]; sectionName = articleInfo[1]; url = articleInfo[2]
            headline = articleInfo[3]; bodyText = articleInfo[4]
            articleTable.append((pubName, sectionName, url, headline, Analyzer.cutBodyText(bodyText))) #Append to table
   
   print("Total article count:", len(articleTable))
   #Send the request through Analyzer module
   Analyzer.createBatch_CategoricalEval(articleTable, startIndex, confirmMsg)

"""
=========================================================
               CALCULATIONS / VISUALIZATION
=========================================================
"""

#Calculates the overall political rating of every publication and writes to file
def calculatePublicationPoliticsRating():
   pubRatingDict = {}

   #Read article ratings from article politics eval file
   with open(Analyzer.politicsEvalFileName, "r") as csvF:
      csvReader = csv.reader(csvF)
      csvContent = [line for line in csvReader]

      for articleInfo in csvContent:
         pubName = articleInfo[0]
         if pubName not in pubRatingDict: pubRatingDict[pubName] = []

         evalRating = articleInfo[3].split(" | ")[0]
         try: #Catch conversion errors just in case
            rating = float(evalRating)
         except Exception as e:
            rating = 0.0
         
         pubRatingDict[pubName].append(rating)
   

   with open(pubPoliticsFileName, "w") as csvF:
      csvWriter = csv.writer(csvF)
      for pubName in list(pubRatingDict.keys()):
         csvWriter.writerow([pubName, Analyzer.calculatePublicationPolitics(pubRatingDict[pubName])]) #Write publication rating
   
#Calculates the overall political rating of every city and writes to file
def calculateCityPoliticalRating():
   locRatings = {} #Format {state -> {city -> rating}}

   #Calculate political rating of each city
   for state in list(cityPubDict.keys()):
      for city in list(cityPubDict[state].keys()):
         pubRatings = cityPubDict[state][city]
         ratingList = []
         for name, rating in pubRatings: #Convert [(school name, rating),...] to a list of [rating,...]
            ratingList.append(rating)
         
         if state not in locRatings: locRatings[state] = {}
         locRatings[state][city] = Analyzer.calculateCityPolitics(ratingList) #Save calculation

   #Write to city politics file
   with open(cityPoliticsFileName, "w") as csvF:
      csvWriter = csv.writer(csvF)
      for state in list(locRatings.keys()):
         for city in list(locRatings[state].keys()):
            csvWriter.writerow([state, city, locRatings[state][city]])

#Organize publication political ratings by state
def organizePoliticsByState():
   with open(statePoliticsFileName, "w") as csvF:
      csvWriter = csv.writer(csvF)
      for state in list(cityPubDict.keys()):
         pubsInState = [state] #Format [state, (pubName, pubRating),...]
         for city in list(cityPubDict[state].keys()):
            for pubInfo in cityPubDict[state][city]:
               pubsInState.append(pubInfo)
         csvWriter.writerow(pubsInState)

#Organize publication political ratings by liberal (blue) or conservative (red), comparing with general voter data
def organizePoliticsByParty():
   with open(zonePoliticsFileName, "w") as csvF:
      csvWriter = csv.writer(csvF)
      pubsByParty = [["Liberal (Blue)"], ["Conservative (Red)"]] #Format [[liberal, "pubName, pubRating", ...], [conserv, ...]]
      for state in list(cityPubDict.keys()):
         for city in list(cityPubDict[state].keys()):
            for pubName, pubRating in cityPubDict[state][city]:
               county = Visualizer.getCounty(city, state)
               if not county: continue
               gop_ratio, dem_ratio = Visualizer.getCountyPolitics(county)
               if not gop_ratio: continue
               if gop_ratio < 0.5:
                  pubsByParty[0].append(pubName + "," + str(pubRating))
               else:
                  pubsByParty[1].append(pubName + "," + str(pubRating))
      csvWriter.writerow(pubsByParty[0])
      csvWriter.writerow(pubsByParty[1])

#Compile all publication political ratings matched with their county voter data 
def organizeFullPolitics():
   with open(fullPoliticsFileName, "w") as csvF:
      csvWriter = csv.writer(csvF)
      csvWriter.writerow(["Name","City","State","Pub. Rating","County","GOP %", "Dem %"])
      for state in list(cityPubDict.keys()):
         for city in list(cityPubDict[state].keys()):
            for pubName, pubRating in cityPubDict[state][city]:
               county = Visualizer.getCounty(city, state)
               if not county: continue
               gop_ratio, dem_ratio = Visualizer.getCountyPolitics(county)
               if not gop_ratio: continue
               csvWriter.writerow([pubName, city, state, pubRating, county.title(), gop_ratio, dem_ratio])

#Creates a comprehensive U.S. map visualization of all high school publication cities
"""
Modes:
- "default": Original political rating value per city
- "median": Relative to the country median rating
- "0_1_median": Same as "median" mode, but only solid red or solid blue, no gradient
"""
def generatePublicationsMapByCity(mode="default", writeToFile=False):
   #Calculate the median (for relative analysis)
   allRatings = []
   with open(cityPoliticsFileName, "r") as csvF:
      csvReader = csv.reader(csvF)
      csvContent = [line for line in csvReader]
      for locInfo in csvContent:
         state = locInfo[0]
         city = locInfo[1]
         rating = locInfo[2]
         allRatings.append(float(rating))
   
   relative_point = 0.0
   if mode == "median" or mode == "0_1_median": relative_point = allRatings[len(allRatings)//2]

   #Read from publication file
   with open(cityPoliticsFileName, "r") as csvF:
      csvReader = csv.reader(csvF)
      csvContent = [line for line in csvReader]

      for locInfo in csvContent:
         state = locInfo[0]
         city = locInfo[1]
         rating = float(locInfo[2]) - relative_point
         if mode == "0_1_median": rating = -10.0 if rating < 0 else 10.0
         Visualizer.addCity(city, state, rating, cityPubDict[state][city])

   Visualizer.showCityMap(writeToFile=writeToFile)

"""<<Control Center>>"""

#===Publication scraping===#
#getPublicationData()
#abridgePublicationData(pubsFileName, 5, 6242007)
createPublicationInfoDict()

#===Article scraping===#
#getArticleURLs()
#getArticleInfo()
#abridgeArticleInfo(infoFileName)
createArticleInfoDict()

#===AI Analysis===#
#sendRequest_ArticlesBWPolitics(confirmMsg=False)
#sendRequest_ArticlesEvalPolitics(confirmMsg=False, fileLineStart=95165)
#sendRequest_ArticlesCategoricalTopics(confirmMsg=True, fileLineStart=1, readFromStorage=True)
createArticleRatingDict()
createCityPoliticalDict()
createCountyPoliticalDict()
createCategoryDict()

#===Calculations/Visualization===#
calculatePublicationPoliticsRating()
calculateCityPoliticalRating()
organizePoliticsByState()
organizePoliticsByParty()
organizeFullPolitics()
#generatePublicationsMapByCity(mode="default",writeToFile=True)
Visualizer.showWordCloud(catDict)


"""
Instructions on how to scrape by state:
1) Cut all schools from desired state from publications_source to publications_test
2) Run 'Article scraping' block (uncomment code)
3) Run BW analysis
4) Run political evaluation (note the fileLineStart)
5) Run 'Calculations/Visualizations' block (uncomment code) to visualize data
6) Change fileLineStart in political evaluation function to the next line in article_politics_bw
"""