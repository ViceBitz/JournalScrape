from bs4 import BeautifulSoup
import httplib2
import csv

"""
Data-scrapes information of all high school publications from the SNO (snosites.com) network,
which includes a wide plethora of schools (~2500) across all 50 states + 19 international countries.
Finds publication name, state, city, and link to their online news website.

@author Victor Gong
@version 7/27/2024
"""

#Scrapes all high school online journalism websites from SNO platform and returns a table of tuples (name, state, city, link)
def scrapePublicationURLs():
   snoURL = "https://snosites.com/our-customers/high-schools/"
   snoHTTP = httplib2.Http()

   response, snoHTML = snoHTTP.request(snoURL)

   soup = BeautifulSoup(snoHTML, features="html.parser")
   tables = soup.findChildren('table')

   #Table for tracking & returning publication info
   publications = [] 

   #Sets for echoing
   statesList = set()
   citiesList = set()

   #Scrap by table->row(tr)->cell(td)->a->link(href)
   for t in tables:
      rows = t.findChildren(["tr"]) #Get all rows
      pubState = t.find("th").text #Get which state in the U.S. this table covers

      statesList.add(pubState)

      for r in rows:
         infoCell = r.find("td", {"class":"newspaper"}) #Get cell with name/city
         linkCell = r.find("td", {"class":"sitelink"}) #Get cell with sitelink

         if infoCell == None or linkCell == None: continue #Skip if not a publication row
         
         pubInfo = infoCell.text.split(" in ")
         pubName, pubCity = pubInfo[0], pubInfo[1]
         pubLink = linkCell.find("a")["href"]

         citiesList.add(pubCity)

         publications.append((pubName.strip(), pubState.strip(), pubCity.strip(), pubLink))

   #Echo stats
   print("Publication scrape stats:\n=========================\n-",
         len(publications),"high school publications\n-",
         len(citiesList),"cities\n-",
         len(statesList),"states/countries\n")
   
   return publications