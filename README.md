# JournalScrape: AI Social Scraping 
Large-scale data pipeline that scrapes articles from across journalism publications and uncovers political trends via ChatGPT-4o LLM, content filtering, and bias scoring.
Research paper: https://doi.org/10.59720/24-277

## Overview
This social-scraping framework consists of three key stages:
1.  Content Extraction: finding school news sites, extracting article data, and organizing into CSV
2.  Political Filtering: eliminating politically neutral articles from consideration
3.   NLP Analysis: using LLMs to analyze summarized article text, categorizing topics and calculating political lean score

targeting three common sections (opinions, features, news), and scraping headlines & body text from ~30 latest article of each section

---
## Usage
The pipeline consists of dozens of methods for each step, all of which is gathered here in the code:
```
"""<<Control Center>>"""

#===Publication scraping===#
getPublicationData()
abridgePublicationData(pubsFileName, 5, 6242007)
createPublicationInfoDict()

#===Article scraping===#
getArticleURLs()
getArticleInfo()
abridgeArticleInfo(infoFileName)
createArticleInfoDict()

#===AI Analysis===#
sendRequest_ArticlesBWPolitics(confirmMsg=False)
sendRequest_ArticlesEvalPolitics(confirmMsg=False, fileLineStart=95165)
sendRequest_ArticlesCategoricalTopics(confirmMsg=True, fileLineStart=1, readFromStorage=True)
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
generatePublicationsMapByCity(mode="default",writeToFile=True)
Visualizer.showWordCloud(catDict)
```
Because of the large dataset, it's recommended to scrape publications and articles in chunks by state and analyze text in batches (articles total to over 45 million words!). Follow this general pipeline methodology:
1) Cut all schools from desired state from publications_source to publications_test
2) Run 'Article scraping' block (uncomment code)
3) Run BW analysis
4) Run political evaluation (note the fileLineStart)
5) Run 'Calculations/Visualizations' block (uncomment code) to visualize data
6) Change fileLineStart in political evaluation function to the next line in article_politics_bw

---

### ⛏️ Article Extraction
Most high school publications post their articles on online news-sites managed by School Newspapers Online (SNO), a service that offers website templates for journalism purposes. 

JournalScrape collects publication URLs from SNO's customer database. To maximize politically-related articles, I targeted three key sections: opinions, features, and news, on each site. The program then scraped the body text, date, and headline from ~30 of the latest articles of each section for further processing.

### 🔍 Content Filtering
After collecting article data, we filter out any unrelated or erroneous content. This includes articles that are way too short for consideration (<250 words) or are simply politically neutral.

JournalScrape employs Python's NLTK library to condense article text and ChatGPT-4o mini to analyze the summary and headline, determining if the content is relevant enough for further analysis. URLs that returned a 404 code (can't be found) were also ignored during Content Extraction as well as this stage.

### 📊 Political Analysis
Articles that pass the filtering stage move on to political analysis, where their subject matter is categorized into one of 30 popular issues listed on the U.S. Department of State website. JournalScrape also assigns each article a bias score on a scale of -42 (very liberal) to 42 (very conservation).

These data points were later visualized through a scattermap of averaged political scores by city on a U.S. map, a distribution of a publication overall political lean score split by historically liberal-voting or conversative-voting counties, and a word cloud / frequency chart of popular topics across all articles, along with the average political stance per topic.

