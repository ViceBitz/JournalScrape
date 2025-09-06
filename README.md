# JournalScrape: AI Social Scraping 
Large-scale data pipeline that scrapes articles from across journalism publications and uncovers political trends via ChatGPT-4o LLM, content filtering, and bias scoring.
Research paper: https://doi.org/10.59720/24-277

## Overview
This social-scraping framework consists of three key stages:
1.  Content Extraction: finding school news sites, extracting article data, and organizing into CSV
2.  Political Filtering: eliminating politically neutral articles from consideration
3.   NLP Analysis: using LLMs to analyze summarized article text, categorizing topics and calculating political lean score

targeting three common sections (opinions, features, news), and scraping headlines & body text from ~30 latest article of each section
 

### Content Extraction
Most high school publications post their articles on online news-sites managed by School Newspapers Online (SNO), a service that offers website templates for journalism purposes. 

JournalScrape collects publication URLs from SNO's customer database. To maximize politically-related articles, I targeted three key sections: opinions, features, and news, on each site. The program then scraped the body text, date, and headline from ~30 of the latest articles of each section for further processing.

### Political Filtering
After collecting article data, the next step naturally is to weed out any unrelated or erroneous content. This includes articles that are way too short for consideration (<250 words) or are simply political neutral.

JournalScrape employs ChatGPT-4o mini for this process, quickly analyzing a summary of the article text and the headline to determine if the content is relevant for more analysis. URL that returned a 404 code (can't be found) were also ignored during Content Extraction as well as this stage.

### NLP Analysis
Articles that pass the filtering stage move on to political analysis, where their subject matter is categorized into one of 30 popular issues listed on the U.S. Department of State website. JournalScrape also assigns each article a bias score on a scale of -42 (very liberal) to 42 (very conservation).

These data points were later visualized through a scattermap of averaged political scores by city on a U.S. map, a distribution of a publication overall political lean score split by historically liberal-voting or conversative-voting counties, and a word cloud / frequency chart of popular topics across all articles, along with the average political stance per topic.

