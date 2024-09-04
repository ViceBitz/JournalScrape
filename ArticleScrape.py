from bs4 import BeautifulSoup
import requests

"""
Extracts headline (and subhead), publishing date, and article body text from
a given article URL.

@author Victor Gong
@version 7/27/2024
"""

#Scrapes the headline, date, and body text
#Returns tuple in the format (URL, headline, date, bodyText)
def scrapeArticle(articleURL):
   try:
      articleHTML = requests.get(articleURL).content
   except Exception as e:
      return (None, None, None, None)
   soup = BeautifulSoup(articleHTML, features="html.parser")

   #Get headline from <h1 class="sno-story-headline"> element
   headlineEle = soup.find("h1",{"class": "sno-story-headline"})
   if headlineEle == None: headlineEle = soup.find("h1",{"class":"storyheadline"})
   if headlineEle == None: return (None, None, None, None)
   
   headline = headlineEle.text

   #Get publish date from <span class="time-wrapper"> element
   dateEle = soup.find("span",{"class": "time-wrapper"})
   if dateEle == None: return (None, None, None, None)
   publishDate = dateEle.text

   #Get article body from all paragraph elements <p>
   bodyEle = soup.find("div", {"id":"sno-story-body-content"})
   if bodyEle == None: bodyEle = soup.find("span",{"class":"storycontent"})
   if bodyEle == None: return (None, None, None, None)
   
   bodyText = ""
   for g in bodyEle.findChildren("p",{"class":None}): #Take text without class (no pullquotes)
      bodyText += g.get_text().replace("\n","")
   

   return (articleURL, headline.strip(), publishDate.strip(), bodyText.strip())



   