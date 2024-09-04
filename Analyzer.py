from openai import OpenAI
import nltk
import nltk
import ssl
import json, ujson, csv
from pathlib import Path
import time
import math
client = OpenAI(api_key = "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")

#Download NLTK Punkt package (comment out if done)
"""
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context
nltk.download('punkt')
"""

"""
Analyzes a given article in the realm of politics and entertainment, utilizing the GPT model
to deduce factors like partisanship or general trends.

@author Victor Gong
@version 7/27/2024
"""

#Batch in/out filenames
batchBWInFileName = "requests_in/batch_politics_bw_in.jsonl" #Black-white political analysis batch IN file
batchEvalInFileName = "requests_in/batch_politics_eval_in.jsonl" #Political evaluation batch IN file
batchCatInFileName = "requests_in/batch_politics_cat_in.jsonl" #Categorical sorting batch IN file

batchBWOutFileName = "requests_out/batch_politics_bw_out.jsonl" #Black-white political analysis batch OUT file
batchEvalOutFileName = "requests_out/batch_politics_eval_out.jsonl" #Political evaluation batch OUT file
batchCatOutFileName = "requests_out/batch_politics_cat_out.jsonl" #Categorical sorting batch OUT file

#Result filenames
politicsBWFileName = "results/article_politics_bw.csv" #Black-white political analysis for all articles
politicsEvalFileName = "results/article_politics_eval.csv" #Full political evaluation for all articles
politicsCatFileName = "results/article_politics_cat.csv" #Categorical topic sorting for all articles

#Log filenames
logBWFileName = "log/politics_bw_log.csv"
logEvalFileName = "log/politics_eval_log.csv"
logCatFileName = "log/politics_cat_log.csv"

TEXT_MIN_CUTOFF = 500 #Articles under this limit won't be considered
TEXT_MAX_CUTOFF = 1000 #Articles over this limit will be trimmed to the limit

MAX_BATCH_TOKENS_BW = 200000 #Max tokens can send per batch for BW
MAX_BATCH_TOKENS_CAT = 20000000-50000 #20000000 Max tokens can send per batch for categorical
MAX_BATCH_TOKENS_EVAL = 90000 #Max tokens can send per batch for eval

"""
=========================================================
               ARTICLE PREPROCESSING / MISC
=========================================================
"""
#Cuts a longer body text into a shorter version (~1500 characters) to reduce GPT usage costs
def cutBodyText(bodyText):
   cutoff = TEXT_MAX_CUTOFF
   tokenizer = nltk.data.load("tokenizers/punkt/english.pickle")
   sentences = tokenizer.tokenize(bodyText)

   outTextFront = ""
   it = 0
   #Get beginning of article
   for sentence in sentences:
      outTextFront += sentence + " "; it+=1
      if len(outTextFront) >= cutoff/2:
         break
   
   outTextBack = ""
   for i in range(len(sentences)-1,it,-1):
      outTextBack = " " + sentences[i] + outTextBack
      if len(outTextBack) >= cutoff/2:
         break
   
   return outTextFront + outTextBack

#Checks if body text is too short to consider
def articleTooShort(bodyText):
   return len(bodyText) < TEXT_MIN_CUTOFF

#Helper functions to read and write to jsonl
def read_jsonl(file_path):
    with Path(file_path).open('r', encoding='utf8') as f:
        for line in f:
            try:  # hack to handle broken jsonl
                yield ujson.loads(line.strip())
            except ValueError:
                continue
def write_jsonl(file_path, lines):
   data = [ujson.dumps(line, escape_forward_slashes=False) for line in lines]
   Path(file_path).open('w', encoding='utf-8').write('\n'.join(data))

"""
=========================================================
                  PROMPT GENERATION
=========================================================
"""
#Generates the prompt table to ask GPT-3.5 for black-white analysis (if the article is political or not)
def generatePrompts_BW(headline, bodyText):
   prompts = [{"role":"system", "content":"You are an intelligent political scientist."}]

   #Check if article is even remotely related to politics or not
   prompts.append({"role":"user", "content":"Take into account this article with headline '" + headline + "' and body text'" +bodyText+"',"+
                   "Is this article related to any social or political stances/ideas/topics at all? Answer with strictly Y or N"})
   
   return prompts

#Generate the prompt table to ask GPT-4o for political evaluation rating
def generatePrompts_PoliticalEval(headline, bodyText):
   prompts = [{"role":"system", "content":"You are an intelligent political scientist."}]

   #Ask for political rating
   prompts.append({"role":"user","content":"Assign a political lean score on scale of -42 (left) to 42 (right) to this article, HEADLINE:'"
               + headline + "' and BODY TEXT: '" + bodyText + "' Try not 0.0, specific and precise, one sig. fig. Format: number | 1-word justification"})
   return prompts

#Generate the prompt table to ask GPT-4o-mini for categorical topic evaluation
def generatePrompts_CategoricalEval(headline, bodyText):
   #Inspiration: https://www.state.gov/policy-issues/
   presetTopics = ["education reform", "geopolitics","Russia-Ukraine War","Israel-Hamas War","diversity & inclusion",
                   "democracy","humanitarian","LGTBQ","feminism","death penalty","religion","human rights",
                   "economy","cost of living","consumerism","health care","abortion","climate change",
                   "environmental issues","racism","renewable energy","cyber security","technology & innovation",
                   "crime","mental health","cultural critique","gun control","drugs","terrorism","immigration"]
   prompts = [{"role":"system", "content":"You are an intelligent political scientist."}]

   #Ask for category placement
   prompts.append({"role":"user","content":"Sort this article into a category, HEADLINE:'"
               + headline + "' and BODY TEXT: '" + bodyText + "' | Category List: " + ",".join(presetTopics) + " | " 
               + "Respond with ONLY ONE category in this list, nothing more."})
   return prompts

"""
=========================================================
                        AI ANALYSIS
=========================================================
"""

#Finalizes and sends a batch request to ChatGPT API given requests file
def finalizeBatch(reqsFileName, desc, confirmMsg):
   #Send to Batch API
   confirmMsg = input("Double check "+reqsFileName+" for correct info: (1) Confirm, (2) Cancel\n") if confirmMsg else "1"
   if confirmMsg == "1":
      batch_input_file = client.files.create(
         file=open(reqsFileName, "rb"),
         purpose="batch"
      )
      file_id = batch_input_file.id

      batch = client.batches.create(
         input_file_id=file_id,
         endpoint="/v1/chat/completions",
         completion_window="24h",
         metadata={"description" : desc}
      )
      print("Successfully created batch, batch id:",batch.id)
      return batch
   return None

#Retrieves the output/results file of a specific batch and writes article info and response to json and csv files
def retrieveBatchResult(batch, jsonFileName, csvFileName):
   if batch.status == "completed":
      batchResult = client.files.content(batch.output_file_id).content
      with open(jsonFileName, "wb") as f: #Write to raw .jsonl file
         f.write(batchResult)

      results = []
      with open(jsonFileName, "r") as f: #Read results from raw .jsonl file
         for line in f:
            json_obj = json.loads(line.strip())
            results.append(json_obj)
      
      articleCount = 0
      with open(csvFileName, "a") as csvF: #Append article info and responses to .csv file
         csvWriter = csv.writer(csvF)
         for res in results:
            articleInfo = res["custom_id"].split("|") #School name, section name, article URL
            response = res["response"]["body"]["choices"][0]["message"]["content"]
            csvWriter.writerow([articleInfo[0], articleInfo[1], articleInfo[2], response])
            articleCount+=1
      print(batch.id, "successfully processed:",articleCount,"articles")
   else:
      print(batch.id, "|", batch.status)

#Politically analyzes an article given its headline and body text (only takes ~350 words cumulative from beginning and end)
#Deduces if the article is partisan, and if so, which party it supports and to what degree.
#Returns a number on a scale of -42 (Extreme Left) to 42 (Extreme Right)), and if the article is related to politics

#!!*For cost and efficiency, this method is deprecated: send bulk articles via GPT batch API system

def politicsAnalyze(headline, bodyText):
   chat_comp = client.chat.completions.create(model="gpt-3.5-turbo-0125", messages=generatePrompts_BW(headline, bodyText))
   isPolitical = chat_comp.choices[0].message.content

   if "y" in isPolitical.lower():
      chat_comp = client.chat.completions.create(model="gpt-4o-2024-05-13", messages=generatePrompts_PoliticalEval(headline, bodyText), temperature=0.6, top_p=0.5)
      rating = chat_comp.choices[0].message.content.split(" | ")

      #Try to convert to number
      if len(rating) < 2: return 0.0, "Not political"
      try:
         return float(rating[0]), rating[1]
      except ValueError:
         return 0.0, "Error"
   else:
      return 0.0, "Not political"
   
"""
=========================================================
                        BATCH API
=========================================================
"""

#Writes article information to .json and sends batch request to GPT-3.5 for black white analysis (is/is not political)
#Takes in table in the format [(pubName, pubSection, articleURL, headline, bodyText),...]
def createBatch_BWAnalysis(allArticles, startIndex=0, confirmMsg=True):
   #Send in multiple batches to not exceed limit
   index = startIndex
   while (index < len(allArticles)):
      totalCharacters = 0
      previousIndex = index
      dataList = []
      #Create data table
      for i in range(index, len(allArticles)):
         name, section, url, headline, bodyText = allArticles[i]
         prompts = generatePrompts_BW(headline, bodyText) #Generate prompts

         for p in prompts: totalCharacters += len(p["content"])
         if totalCharacters > MAX_BATCH_TOKENS_BW*3.5: #If over limit, stop and send batch
            for p in prompts: totalCharacters -= len(p["content"])
            break
         index = i

         #Format request
         data = { 
            "custom_id" : name + "|" + section + "|" + url,
            "method" : "POST",
            "url" : "/v1/chat/completions", 
            "body" : {
               "model" : "gpt-3.5-turbo-0125",
               "messages" :  prompts,
               "max_tokens" : 8
            }
         }
         dataList.append(data)
      index+=1 #Advance to next start point

      #Write to .jsonl
      write_jsonl(batchBWInFileName, dataList)

      #Echo results
      print("Wrote",len(dataList),"articles ["+str(previousIndex),"-",str(index-1)+"] to",batchBWInFileName)
      print("Total characters:",totalCharacters,"| Average characters per article:",(totalCharacters/len(dataList)))
      print("Tokens used:",(totalCharacters/4),"| Predicted cost: ",(totalCharacters/4*0.25/1e6),"| GPT-3.5")
      with open(logBWFileName, "a") as csvF: #Log end index to file
         csvWriter = csv.writer(csvF)
         csvWriter.writerow(["Last ended index: " + str(index)])

      #Create batch and wait for completion
      batch = finalizeBatch(batchBWInFileName, "Black-white political analysis of articles", confirmMsg)
      if batch == None: return #Cancelled

      while (batch.status not in ["completed","failed","cancelled"]):
         time.sleep(3)
         batch = client.batches.retrieve(batch.id)

      retrieveBatchResult(batch, batchBWOutFileName, politicsBWFileName)

#Writes article information .json and sends batch request to GPT-4o for political rating/lean evaluation
#Takes in table in the format [(pubName, pubSection, articleURL, headline, bodyText),...]
def createBatch_PoliticalEval(allArticles, startIndex=0, confirmMsg=True):
   #Send in multiple batches to not exceed limit
   index = startIndex
   while (index < len(allArticles)):
      totalCharacters = 0
      previousIndex = index
      dataList = []
      #Create data table
      for i in range(index, len(allArticles)):
         name, section, url, headline, bodyText = allArticles[i]
         prompts = generatePrompts_PoliticalEval(headline, bodyText) #Generate prompts

         for p in prompts: totalCharacters += len(p["content"])
         if totalCharacters > MAX_BATCH_TOKENS_EVAL*3.5: #If over limit, stop and send batch
            for p in prompts: totalCharacters -= len(p["content"])
            break
         index = i
         
         #Format request
         data = { 
            "custom_id" : name + "|" + section + "|" + url,
            "method" : "POST",
            "url" : "/v1/chat/completions", 
            "body" : {
               "model" : "gpt-4o-2024-05-13",
               "messages" :  prompts,
               "max_tokens" : 8
            }
         }
         dataList.append(data)
      index+=1 #Advance to next start point

      #Write to .jsonl
      write_jsonl(batchEvalInFileName, dataList)

      #Echo results
      print("Wrote",len(dataList),"articles ["+str(previousIndex),"-",str(index-1)+"] to",batchEvalInFileName)
      print("Total characters:",totalCharacters,"| Average characters per article:",(totalCharacters/len(dataList)))
      print("Tokens used:",(totalCharacters/4),"| Predicted cost: ",(totalCharacters/4*2.50/1e6),"| GPT-4o")
      with open(logEvalFileName, "a") as csvF: #Log end index to file
         csvWriter = csv.writer(csvF)
         csvWriter.writerow(["Last ended index: " + str(index)])

      #Create batch and wait for completion
      batch = finalizeBatch(batchEvalInFileName, "Political evaluation of articles", confirmMsg)
      if batch == None: return #Cancelled

      while (batch.status not in ["completed","failed","cancelled"]):
         time.sleep(3)
         batch = client.batches.retrieve(batch.id)

      retrieveBatchResult(batch, batchEvalOutFileName, politicsEvalFileName)

#Writes article information .json and sends batch request to GPT-4o-mini for categorical topic sorting
#Takes in table in the format [(pubName, pubSection, articleURL, headline, bodyText),...]
def createBatch_CategoricalEval(allArticles, startIndex=0, confirmMsg=True):
   #Send in multiple batches to not exceed limit
   index = startIndex
   while (index < len(allArticles)):
      totalCharacters = 0
      previousIndex = index
      dataList = []
      #Create data table
      for i in range(index, len(allArticles)):
         name, section, url, headline, bodyText = allArticles[i]
         prompts = generatePrompts_CategoricalEval(headline, bodyText) #Generate prompts

         for p in prompts: totalCharacters += len(p["content"])
         if totalCharacters > MAX_BATCH_TOKENS_CAT*3.5: #If over limit, stop and send batch
            for p in prompts: totalCharacters -= len(p["content"])
            break
         index = i
         
         #Format request
         data = { 
            "custom_id" : name + "|" + section + "|" + url,
            "method" : "POST",
            "url" : "/v1/chat/completions", 
            "body" : {
               "model" : "gpt-4o-mini",
               "messages" :  prompts,
               "max_tokens" : 8
            }
         }
         dataList.append(data)
      index+=1 #Advance to next start point

      #Write to .jsonl
      write_jsonl(batchCatInFileName, dataList)

      #Echo results
      print("Wrote",len(dataList),"articles ["+str(previousIndex),"-",str(index-1)+"] to",batchCatInFileName)
      print("Total characters:",totalCharacters,"| Average characters per article:",(totalCharacters/len(dataList)))
      print("Tokens used:",(totalCharacters/4),"| Predicted cost: ",(totalCharacters/4*0.075/1e6),"| GPT-4o-mini")
      with open(logCatFileName, "a") as csvF: #Log end index to file
         csvWriter = csv.writer(csvF)
         csvWriter.writerow(["Last ended index: " + str(index)])

      #Create batch and wait for completion
      batch = finalizeBatch(batchCatInFileName, "Political evaluation of articles", confirmMsg)
      if batch == None: return #Cancelled

      while (batch.status not in ["completed","failed","cancelled"]):
         time.sleep(3)
         batch = client.batches.retrieve(batch.id)

      retrieveBatchResult(batch, batchCatOutFileName, politicsCatFileName)

"""
=========================================================
                     CALCULATION
=========================================================
"""

#Calculates the overall political rating of a specific publication by taking the mean square of all article ratings
#Since squaring removes negatives, add it back by calculating in two parts: sqrt([ Σ(-[neg.]^2) + Σ([pos.]^2) ] / (n-1))
def calculatePublicationPolitics(ratings):
   neg_sum = 0.0; pos_sum = 0.0
   for x in ratings:
      if x < 0:
         neg_sum += x**2
      else:
         pos_sum += x**2
   
   sum = ((pos_sum - neg_sum) / len(ratings))
   if sum == 0: return 0 #Avoid divide by zero
   #Get the square root (avoid negative with sqrt(abs(S)) * (S/|S|)
   return math.sqrt(abs(sum)) * sum/abs(sum)

#Calculates the overall political rating of a city by taking the simple (arithmetic) mean
def calculateCityPolitics(ratings):
   sum = 0.0
   for x in ratings:
      sum += x
   return sum / len(ratings)


#Driver code for retrieving specific batch
"""
batchId = "batch_J5nE9rLKmiMEHMOKvakjFiU5"
batch = client.batches.retrieve(batchId)
while (batch.status not in ["completed","failed","cancelled"]):
   time.sleep(3)
   batch = client.batches.retrieve(batch.id)
   print("Pending...")
retrieveBatchResult(batch, batchCatOutFileName, politicsCatFileName)
"""