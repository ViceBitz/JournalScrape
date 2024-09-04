import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import csv
import urllib
import json
import numpy as np
from unidecode import unidecode
from wordcloud import WordCloud
import matplotlib.pyplot as plt

"""
Tool to help visualize cities on the U.S. map. Takes the longitude and latitude of
each city along with other information and creates a map scatter plot.

@author Victor Gong
@version 7/27/2024
"""

#Location data files
citiesFileName = "map/cities.csv" #Source: https://simplemaps.com/data/us-cities
stateLinesFileName = "map/state_lines.geojson" #Source: https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_110m_admin_1_states_provinces_lines.geojson
countyLinesFileName = "map/county_lines.geojson" #Source: https://github.com/plotly/datasets/blob/master/geojson-counties-fips.json
stateAbbrevsFileName = "map/state_abbrevs.csv" #Source: https://github.com/jasonong/List-of-US-States/blob/master/states.csv
zipFileName = "map/zip_codes.csv" #Source: https://www.unitedstateszipcodes.org/zip-code-database/
countyPoliticsFileName = "map/county_politics.csv" #Source: https://github.com/john-guerra/US_Elections_Results/blob/master/US%20presidential%20election%20results%20by%20county.csv
countyFIPSFileName = "map/county_fips.csv" #Source: https://transition.fcc.gov/oet/info/maps/census/fips/fips.txt
#Extra: https://github.com/johan/world.geo.json/tree/master/countries/USA

figureHTMLFileName = "map/map_figure.html" #Saves interactive plotly figure as HTML
figureImgFileName = "map/map_image.png" #Saves plotly figure as static image

#Dictionaries
latLongDict = {} #Format: {state --> {city --> (lat, long)}}
stateAbbrevDict = {} #Format: {state --> abbrev}
countyDict = {} #Format: {state --> {city --> county}}
countyPoliticsDict = {} #Format: {county --> (GOP ratio, Dem ratio)}
countyFIPSDict = {} #Format: {county --> FIP}

lats = []
lons = []
texts = []
colors = []

"""
=========================================================
                  STRINGS / NORMALIZATION
=========================================================
"""
#Normalizes a string by converting special characters (e.g. ñ -> n), removing [.'], and lowercasing
def normStr(str):
   return unidecode(str.lower()).replace(".","").replace("'","").replace("-"," ")

"""
=========================================================
                  COLORS / MAP EFFECTS
=========================================================
"""
#Manual linear interpolation for gradient color (Blue --> White --> Red)
def lerp(a, b, frac):
   return int(a + (b - a) * frac)
def getPoliticalColor(t):
   positions = [-1000, -18, 0, 18, 1000] #Approx. lower/upper bound for ratings)
   colors = [(0,0,255),(0,0,255),(255,255,255),(255,0,0),(255,0,0)] #Colors to interpolate between
   for i in range(len(positions)-1):
      if positions[i] <= t and t <= positions[i+1]:
         frac = (t - positions[i]) / (positions[i+1] - positions[i])
         return (lerp(colors[i][0],colors[i+1][0],frac), lerp(colors[i][1],colors[i+1][1],frac), lerp(colors[i][2],colors[i+1][2],frac))

#Converts rgb to hex
def rgb_hex(rgbColor):
   return '#%02x%02x%02x' % rgbColor
#Gives a label to a rating (e.g. 20 -> "Extreme Conservative")
def getPoliticalRatingAsLabel(rating):
   if rating == 0: return "Neutral"
   positions = [-1000, -12, -5, 0, 5, 12, 1000]
   labels = ["Extreme Liberal", "Moderate Liberal", "Slight Liberal", "Slight Conservative", "Moderate Conservative", "Extreme Conservative"]
   for i in range(len(positions)-1):
      if positions[i] <= rating and rating <= positions[i+1]:
         return labels[i]

"""
=========================================================
                        GETTERS
=========================================================
"""
#Retrieves the latitude and longitude of a specific city in the U.S. with geopy given the city and state name.
def getLatLong(cityName, stateName):
   lat, long = latLongDict[normStr(stateName)][normStr(cityName)]
   return float(lat), float(long)

#Returns the abbreviation of a state
def getStateAbbrev(stateName):
   stateName = normStr(stateName)
   if not stateName or stateName not in stateAbbrevDict: return None
   return stateAbbrevDict[stateName]

#Returns the county given a city and state
def getCounty(cityName, stateName):
   city = normStr(cityName); state = getStateAbbrev(stateName)
   if not state: return None
   state = normStr(state)
   if city not in countyDict[state] and "st " in city: city = city.replace("st ","saint ")
   if city not in countyDict[state]: return None
   return countyDict[state][city]

#Returns the general voter data of a specific county
def getCountyPolitics(countyName):
   county = normStr(countyName)
   if not county in countyPoliticsDict: return None, None
   gop_ratio, dem_ratio = countyPoliticsDict[county]
   return float(gop_ratio), float(dem_ratio)

#Returns the FIPS code of a specific county
def getCountyFIPS(countyName):
   county = normStr(countyName)
   if not county in countyFIPSDict: return None
   return countyFIPSDict[county]


"""
=========================================================
                     DATA RETRIEVAL
=========================================================
"""
#Creates a dictionary of state and city to latitude and longitude
def createLatLongDict():
   with open(citiesFileName, "r") as csvF:
      csvReader = csv.reader(csvF)
      csvContent = [line for line in csvReader]
      for cityInfo in csvContent[1:]:
         city = cityInfo[0]; city = city.replace("'",""); city = normStr(city)
         state = cityInfo[3]; state = state.replace("'",""); state = normStr(state)
         lat = cityInfo[6]; lat = lat.replace("'","")
         long = cityInfo[7]; long = long.replace("'","")
         if state not in latLongDict: latLongDict[state] = {}
         latLongDict[state][city] = (lat, long)

#Creates a dictionary of states to their abbreviations
def createStateAbbrevDict():
   with open(stateAbbrevsFileName, "r") as csvF:
      csvReader = csv.reader(csvF)
      csvContent = [line for line in csvReader]
      for abbrevInfo in csvContent[1:]:
         state = abbrevInfo[0]; abbrev = abbrevInfo[1]; state = normStr(state)
         stateAbbrevDict[state] = abbrev

#Creates a dictionary of states and cities to their respective counties
def createCountyDict():
   with open(zipFileName, "r") as csvF:
      csvReader = csv.reader(csvF)
      csvContent = [line for line in csvReader]
      for zipInfo in csvContent[1:]:
         allCities = zipInfo[4].split(", "); allCities.append(zipInfo[3])
         for x in zipInfo[5].split(", "): allCities.append(x)
         state = zipInfo[6]; state = normStr(state)
         county = zipInfo[7]; county = normStr(county)

         for city in allCities:
            city = city.replace("\"",""); city = normStr(city)
            if state not in countyDict: countyDict[state] = {}
            if city not in countyDict[state] or len(countyDict[state][city]) == 0: #Get rid of repeats / empty strings
               countyDict[state][city] = county

#Creates a dictionary of counties to their political results
def createCountyPoliticsDict():
   with open(countyPoliticsFileName, "r") as csvF:
      csvReader = csv.reader(csvF)
      csvContent = [line for line in csvReader]
      for countyInfo in csvContent[1:]:
         county = countyInfo[1]; county = normStr(county)
         gop_ratio = countyInfo[7]
         dem_ratio = countyInfo[8]
         countyPoliticsDict[county] = (gop_ratio, dem_ratio)

#Creates a dictionary of counties to their FIPS code
def createCountyFIPSDict():
   with open(countyFIPSFileName, "r") as csvF:
      csvReader = csv.reader(csvF)
      csvContent = [line for line in csvReader]
      for countyInfo in csvContent[1:]:
         FIPS = countyInfo[0]; county = normStr(countyInfo[1])
         countyFIPSDict[county] = FIPS
   

"""
=========================================================
                     MAP VISUALIZATION
=========================================================
"""

#Adds a city to the current scattermap
def addCity(cityName, stateName, rating, pubRatings):
   lat, lon = getLatLong(cityName, stateName)
   color = getPoliticalColor(rating)
   ratingText = ("+" if rating >= 0 else "") + str(round(rating, 1))
   ratingLabel = getPoliticalRatingAsLabel(rating)

   lats.append(lat)
   lons.append(lon)
   text =  ("<b>" + cityName.title() + ", " + stateName.title() + "</b><br>" +
            "Rating: " + ratingText + " <i>(" + ratingLabel + ")</i><br><br>" +
            "<b>Schools:</b><br>")
   
   #Sort publications and add as text
   pubRatings = sorted(pubRatings, key=lambda ratingInfo: ratingInfo[0])
   for ratingInfo in pubRatings:
      pubName = ratingInfo[0]
      pubRating = ratingInfo[1]
      pubRatingText = ("+" if pubRating >= 0 else "") + str(round(pubRating, 1))
      text += pubName.title() + ": " + pubRatingText + "<br>"
   
   texts.append(text)
   colors.append(rating)
   #colors.append("rgb"+str(color))

#Shows the scattermap (dotted cities)
def showCityMap(writeToFile=False):
   mapFigure = go.Figure(data=go.Scattergeo(
         lat = lats,
         lon = lons,
         text = texts,
         mode = "markers",
         marker = dict(
            size=10,
            color=colors,
            colorscale=[
               [0,"blue"],
               [0.2,"blue"],
               [0.5,"white"],
               [0.8,"red"],
               [1,"red"],
            ],
            cmin=-30,
            cmax=30,
            colorbar=dict(title='', tickfont=dict(size=18, family="Georgia"))
         ),
         hoverinfo="text",
         hovertemplate="%{text}<extra></extra>",
         showlegend=False
   ))
   mapFigure.update_layout(
      title=dict(text="Political Leans of High School Publications By City", font=dict(size=24, family="Georgia", color="black"), x=0.5)
   )
   #Show state boundaries
   with open(stateLinesFileName, "r") as response:
      states_geojson = json.load(response)
   
   mapFigure = mapFigure.add_trace(
      go.Scattergeo(
        lat=[
            v for sub in [np.array(f["geometry"]["coordinates"])[:, 1].tolist() + [None] for f in states_geojson["features"]]
            for v in sub
        ],
        lon=[
            v for sub in [np.array(f["geometry"]["coordinates"])[:, 0].tolist() + [None] for f in states_geojson["features"]]
            for v in sub
        ],
        line_color="black",
        line_width=1,
        mode="lines",
        showlegend=False,
        hoverinfo="skip"
      )
   )

   mapFigure.update_geos(
      showland=True,
      landcolor="rgb(150,150,150)",
      showlakes=True,
      lakecolor="LightBlue",
      subunitcolor="Black",
      subunitwidth=1,
      scope='usa',
      bgcolor='rgb(255, 255, 255)'
   )

   if writeToFile:
      mapFigure.write_image(figureImgFileName, format="png", scale=3.0)
      mapFigure.write_html(figureHTMLFileName)
   mapFigure.show()

#Shows a chloropleth by county of publication ratings
def showCountyMap(countyPubDict, writeToFile=False): #Takes a dict in the format: {state -> {county -> [(pubName, pubRating),...]}}

   allFIPS = [] #Format: [FIPS,...]
   allRatings = [] #Format: [countyRating,...]
   allTexts = [] #Format: [text,...]
   
   for state in list(countyPubDict.keys()):
      for county in list(countyPubDict[state].keys()):
         FIPS = getCountyFIPS(county)
         if not FIPS: continue
         
         #Calculate county ratings with simple average
         countyRating = 0.0
         for pubName, pubRating in countyPubDict[state][county]:
            countyRating += pubRating
         countyRating /= len(countyPubDict[state][county])
         allFIPS.append(FIPS); allRatings.append(countyRating)
   
         #Add county body text
         ratingText = ("+" if countyRating >= 0 else "") + str(round(countyRating, 1))
         ratingLabel = getPoliticalRatingAsLabel(countyRating)

         text = ("<b>" + county.title() + ", " + state.title() + "</b><br>" +
                  "Rating: " + ratingText + " <i>(" + ratingLabel + ")</i><br><br>" +
                  "<b>Schools:</b><br>")
         
         #Sort publications and add as text
         pubRatings = sorted(countyPubDict[state][county], key=lambda ratingInfo: ratingInfo[0])
         for ratingInfo in pubRatings:
            pubName = ratingInfo[0]
            pubRating = ratingInfo[1]
            pubRatingText = ("+" if pubRating >= 0 else "") + str(round(pubRating, 1))
            text += pubName.title() + ": " + pubRatingText + "<br>"
         
         allTexts.append(text)

   #Show county boundaries
   with open(countyLinesFileName, "r") as response:
      counties_geojson = json.load(response)
   
   #Create county chloropeth figure
   df = pd.DataFrame({
      'fips' : allFIPS,
      'ratings' : allRatings,
      'info' : allTexts
   })
   mapFigure = px.choropleth(
      df,
      geojson=counties_geojson,
      locations='fips',
      color='ratings',
      hover_data={'info':True,'fips':False,'ratings':False},
      color_continuous_scale=[
         (0,"blue"),
         (0.2,"blue"),
         (0.5,"white"),
         (0.8,"red"),
         (1,"red"),
      ],
      range_color=(-30,30),
      labels={'info':''}
   )
   map
   mapFigure.update_layout(
      title=dict(text="Political Leans of High School Publications By County", font=dict(size=24, family="Georgia", color="black"), x=0.5),
      coloraxis_colorbar=dict(
        title=dict(
            text="",
            font=dict(
               family="Georgia",
               size=24,
               color="black"
            )
         )
      )
   )
   mapFigure.update_geos(
      showland=True,
      landcolor="rgb(150,150,150)",
      showlakes=True,
      lakecolor="LightBlue",
      subunitcolor="Black",
      subunitwidth=1,
      scope='usa',
      bgcolor='rgb(255, 255, 255)'
   )

   if writeToFile:
      mapFigure.write_image(figureImgFileName, format="png", scale=3.0)
      mapFigure.write_html(figureHTMLFileName)
   
   mapFigure.show()
   
#Shows a word cloud of all topics discussed in articles
wordCloudTable = {}
def showWordCloud(wordTable): #Takes a list in the format: [(word, frequency, avg. political lean),...]
   freqTable = {}
   for word in list(wordTable.keys()):
      freqTable[word] = wordTable[word][0]
   
   global wordCloudTable
   wordCloudTable = wordTable #Make accessible to color function
   
   wc = WordCloud(background_color="black", width=1250, height=1250, relative_scaling=0.1, collocations=False).generate_from_frequencies(freqTable)
   plt.imshow(wc.recolor(color_func=wordCloud_color_func))
   plt.axis("off")
   plt.grid(visible=False)
   plt.show()
def wordCloud_color_func(word, **kwargs):
   return rgb_hex(getPoliticalColor(wordCloudTable[word][1]))



#Create all lookup dictionaries
createLatLongDict()
createStateAbbrevDict()
createCountyDict()
createCountyPoliticsDict()
createCountyFIPSDict()