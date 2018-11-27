import xml.etree.ElementTree as ET
from zipfile import ZipFile
import dateutil.parser, datetime, calendar, time
import requests, io, os
import math
from openhab import openHAB

# Input
interval_hours = 3
forecasts_h = 8
forecasts_d = 6
url_dwd = "https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_L/single_stations/K2791/kml/MOSMIX_L_LATEST_K2791.kmz"
offline_filename = "/etc/openhab2/scripts/MOSMIX_L_LATEST_K2791.kmz"
folder_icons = "/static/dwd/icons/"
max_age_offline_file = 5 # days
kelvin = -273.15
url_oh = 'http://openhabianpi:8080/rest'

# Functions
def error_loading(status_code):
    print("Fehler beim Laden der Daten. Fehlercode: " + str(status_code))
    print("Auch keine lokale kmz Datei gefunden.")
    # set OH items to 0 or unknown
    for step in range(forecasts_h):
        time_hour = ((dt_last_interval_start_local.hour + interval_hours*step) % 24)
        if (time_hour >= 21) or (time_hour < 6):
            day_night = "Nacht"
        else:
            day_night = "Tag"
    send_oh('DWD_Vorhersage_h_Zeit_'+str(step),time_hour)
    send_oh('DWD_Vorhersage_h_TagNacht_'+str(step),day_night)
    send_oh('DWD_Vorhersage_h_Icon_'+str(step),folder_icons+"unknown.png")
    send_oh('DWD_Vorhersage_h_Temp_'+str(step),0.0)
    send_oh('DWD_Vorhersage_h_Taupunkt_'+str(step),0.0)
    send_oh('DWD_Vorhersage_h_Luftfeuchtigkeit_'+str(step),0)
    send_oh('DWD_Vorhersage_h_Regen_'+str(step),0.0)
    send_oh('DWD_Vorhersage_h_Regenwahrscheinlichkeit_'+str(step),0.0)
    send_oh('DWD_Vorhersage_h_Wind_'+str(step),0.0)
    send_oh('DWD_Vorhersage_h_maxWind_'+str(step),0.0)
    send_oh('DWD_Vorhersage_h_Temp_max',1.0) # set to one, so that no value matches max or min
    send_oh('DWD_Vorhersage_h_Temp_min',1.0)
    for day in range(2,forecasts_d):
        day_name = (dt_today_local + datetime.timedelta(days=day)).strftime('%A')
        day_name_translated = translate_weekday(day_name)
        send_oh('DWD_Vorhersage_d_Tag_'+str(day),day_name_translated)
    for day in range(forecasts_d):
        send_oh('DWD_Vorhersage_d_Tempmax_'+str(day),0.0)
        send_oh('DWD_Vorhersage_d_Tempmin_'+str(day),0.0)
        send_oh('DWD_Vorhersage_d_Regen_'+str(day),0.0)
        send_oh('DWD_Vorhersage_d_Regenwahrscheinlichkeit_'+str(day),0.0)
        send_oh('DWD_Vorhersage_d_Wolken_'+str(day),0)
        send_oh('DWD_Vorhersage_d_Sonnenstunden_'+str(day),0.0)
        send_oh('DWD_Vorhersage_d_SonnenstundenProzent_'+str(day),0.0)
        send_oh('DWD_Vorhersage_d_Icon_'+str(day),folder_icons+"unknown.png")
    send_oh('DWD_Vorhersage_d_Tempmax_max',1.0)
    send_oh('DWD_Vorhersage_d_Tempmin_min',1.0)
    exit()

def isfloat(value):
    try:
        float(value)
        return True
    except ValueError:
        return False

def read_forecast(data, value, offset=0.0):
    for forecast_element in data.findall('dwd:Forecast', namespaces):
        if forecast_element.attrib['{https://opendata.dwd.de/weather/lib/pointforecast_dwd_extension_V1_0.xsd}elementName']==value:
            read_string = forecast_element.findall('dwd:value', namespaces)[0].text
            read_list = []
            for elem in read_string.split():
                if isfloat(elem):
                    read_list.append(float(elem) + offset)
                else:
                    read_list.append(float('NaN'))
    return read_list

def rel_humid(T2m, TD2m):
    rh_c2 = 17.5043
    rh_c3 = 241.2
    rh = 100*math.exp((rh_c2*TD2m/(rh_c3+TD2m))-(rh_c2*T2m/(rh_c3+T2m)))
    if rh > 100:
        rh = 100.0
    return rh

def code_day(ww_code):
    codes = {
        0: "weather_3", # wolkenlos
        1: "weather_2", # leicht bewoelkt
        2: "weather_2b", # wolkig
        3: "weather_1", # stark bewoelkt/bedeckt
        45: "weather_30", # Nebel
        48: "weather_30b", # Nebel mit Reif
        49: "weather_30b", # Nebel mit Reif
        51: "weather_53", # leichter Spruehregen
        53: "weather_52", # maessiger Spruehregen
        55: "weather_51", # starker Spruehregen
        56: "weather_53b", # leichter Spruehregen, gefrierend
        57: "weather_51b", # maessiger/starker Spruehregen, gefrierend
        61: "weather_16d", # leichter Regen
        63: "weather_16c", # maessiger Regen
        65: "weather_16b", # starker Regen
        66: "weather_16e", # leichter Regen, gefrierend
        67: "weather_16f", # maessiger/starker Regen, gefrierend
        68: "weather_16e", # leichter Schneeregen
        69: "weather_16f", # maessiger/starker Schneeregen
        71: "weather_35b", # leichter Schneefall
        73: "weather_35c", # maessiger Schneefall
        75: "weather_35d", # starker Schneefall
        77: "weather_35c", # Schneegriesel
        80: "weather_6b", # leichter Regenschauer
        81: "weather_6c", # maessiger/starker Regenschauer
        82: "weather_6d", # sehr starker Regenschauer
        83: "weather_16e", # leichter Schneeregenschauen
        84: "weather_16f", # maessiger/starker Schneeregenschauer
        85: "weather_35e", # leichter Schneeschauer
        86: "weather_35f", # maessiger/starker Schneeschauer
        95: "weather_24", # leichtes/maesssiges Gewitter ohne Graupel/Hagel
        96: "weather_23b", # starkes Gewitter ohne Graupel/Hagel
        99: "weather_23c" # starkes Gewitter mit Graupel/Hagel
    }
    return codes.get(ww_code, "unknown")

def code_night(ww_code):
    codes = {
        0: "weather_4", # wolkenlos
        1: "weather_5", # leicht bewoelkt
        2: "weather_5b", # wolkig
        3: "weather_1", # stark bewoelkt/bedeckt
        45: "weather_30", # Nebel
        48: "weather_30b", # Nebel mit Reif
        49: "weather_30b", # Nebel mit Reif
        51: "weather_53", # leichter Spruehregen
        53: "weather_52", # maessiger Spruehregen
        55: "weather_51", # starker Spruehregen
        56: "weather_53b", # leichter Spruehregen, gefrierend
        57: "weather_51b", # maessiger/starker Spruehregen, gefrierend
        61: "weather_16d", # leichter Regen
        63: "weather_16c", # maessiger Regen
        65: "weather_16b", # starker Regen
        66: "weather_16e", # leichter Regen, gefrierend
        67: "weather_16f", # maessiger/starker Regen, gefrierend
        68: "weather_16e", # leichter Schneeregen
        69: "weather_16f", # maessiger/starker Schneeregen
        71: "weather_35b", # leichter Schneefall
        73: "weather_35c", # maessiger Schneefall
        75: "weather_35d", # starker Schneefall
        77: "weather_35c", # Schneegriesel
        80: "weather_6b", # leichter Regenschauer
        81: "weather_6c", # maessiger/starker Regenschauer
        82: "weather_6d", # sehr starker Regenschauer
        83: "weather_16e", # leichter Schneeregenschauen
        84: "weather_16f", # maessiger/starker Schneeregenschauer
        85: "weather_35e", # leichter Schneeschauer
        86: "weather_35f", # maessiger/starker Schneeschauer
        95: "weather_25", # leichtes/maesssiges Gewitter ohne Graupel/Hagel
        96: "weather_23b", # starkes Gewitter ohne Graupel/Hagel
        99: "weather_23c" # starkes Gewitter mit Graupel/Hagel
    }
    return codes.get(ww_code, "unknown")

def translate_weekday(weekday):
    days = {
        "Monday": "Montag",
        "Tuesday": "Dienstag",
        "Wednesday": "Mittwoch",
        "Thursday": "Donnerstag",
        "Friday": "Freitag",
        "Saturday": "Samstag",
        "Sunday": "Sonntag"
    }
    return days.get(weekday, weekday) # if not found (e.g. because values are already german), use current value

def send_oh(item, value, index=float('nan')):
    try: # an error should not lead to a stop of the script
        if index >= 0:
#            print(item + ": " + str(value[index]))
            Items.get(item).state = value[index]
        else:
#            print(item + ": " + str(value))
            Items.get(item).state = value
    except Exception as e:
        print(e)
        pass

def nan_max(values): # values contain NaNs, normal max() would deliver nan
    floats = []
    for i in values:
        if not math.isnan(i):
            floats.append(i)
    return max(floats)

def nan_min(values): # values contain NaNs, normal min() would deliver nan
    floats = []
    for i in values:
        if not math.isnan(i):
            floats.append(i)
    return min(floats)

# Start your work, python
# Check age of offline file
if os.path.exists(offline_filename):
    age_of_offline_file_days = (time.time() - os.path.getmtime(offline_filename)) / (60*60*24)
    if age_of_offline_file_days > max_age_offline_file:
        os.remove(offline_filename)
        print("Offline File zu alt - entfernt")

# Load Data from DWD
try:
    response = requests.get(url_dwd)
    if response.status_code == requests.codes.ok:
        kmz = ZipFile(io.BytesIO(response.content))
    else:
        try:
            kmz = ZipFile(offline_filename)
        except FileNotFoundError:
            error_loading(response.status_code)
except Exception as e:
    print(e)
    try:
        kmz = ZipFile(offline_filename)
    except FileNotFoundError:
        error_loading(404)
        pass

# Load kml file from zip (kmz-file)
kml = kmz.open(kmz.filelist[0].filename)

# Define Namespaces and load xml data
namespaces = {'dwd': 'https://opendata.dwd.de/weather/lib/pointforecast_dwd_extension_V1_0.xsd', 'kml': 'http://www.opengis.net/kml/2.2'}
tree = ET.parse(kml)
root = tree.getroot()

# Extract available timesteps
timesteps_ts = []
for step in root.findall('kml:Document', namespaces)[0]\
                .findall('kml:ExtendedData', namespaces)[0]\
                .findall('dwd:ProductDefinition', namespaces)[0]\
                .findall('dwd:ForecastTimeSteps', namespaces)[0]\
                .getchildren():
    timesteps_ts.append(calendar.timegm(dateutil.parser.parse(step.text).timetuple())) # timesteps as UNIX timestamps

dt_now_local = datetime.datetime.now()
# First interval starts at midnight. Find the latest start of an interval
dt_last_interval_start_local = datetime.datetime(dt_now_local.year,dt_now_local.month,dt_now_local.day,(dt_now_local.hour // interval_hours)*interval_hours)
# Search the index of this interval start in the available timesteps
# timegm uses UTC, mktime uses local time => get the difference
diff_hours_to_utc = int((calendar.timegm(dt_last_interval_start_local.timetuple())-time.mktime(dt_last_interval_start_local.timetuple())) / 3600)
dt_last_interval_start_utc = dt_last_interval_start_local - datetime.timedelta(hours=diff_hours_to_utc)
ts_last_interval_start_utc = calendar.timegm(dt_last_interval_start_utc.timetuple())
index_last_interval_start = timesteps_ts.index(ts_last_interval_start_utc)
# Calculate index of tomorrow 0:00 UTC
dt_today_local = datetime.date.today()
dt_tomorrow_local = dt_today_local + datetime.timedelta(days=1)
dt_tomorrow_utc = dt_tomorrow_local - datetime.timedelta(hours=diff_hours_to_utc)
ts_tomorrow_utc = calendar.timegm(dt_tomorrow_utc.timetuple())
index_tomorrow_utc = timesteps_ts.index(ts_tomorrow_utc)

# Read Forecasts
data = root.findall('kml:Document', namespaces)[0].findall('kml:Placemark', namespaces)[0].findall('kml:ExtendedData', namespaces)[0]
Temp_2m = read_forecast(data, "TTT", kelvin)
Temp_max_12h = read_forecast(data, "TX", kelvin)
Temp_min_12h = read_forecast(data, "TN", kelvin)
DewPoint_2m = read_forecast(data, "Td", kelvin)
Weather_1h = read_forecast(data, "ww")
Weather_24h = read_forecast(data, "WPch1")
Precipitation_1h = read_forecast(data, "RR1c")
Prob_Precip_1h = read_forecast(data, "R101")
Precipitation_24h = read_forecast(data, "RRdc")
Prob_Precip_24h = read_forecast(data, "Rd10")
Sunshine_24h = read_forecast(data, "SunD") # YESTERDAYS sunshine seconds
RelSunshine_24h = read_forecast(data, "RSunD")
Wind_Speed = read_forecast(data, "FF") # m/s
Wind_Speed_max = read_forecast(data, "FX1")

# calculate rel. humidity
Rel_Humidity = []
for i in range(len(Temp_2m)):
    Rel_Humidity.append(int(rel_humid(Temp_2m[i], DewPoint_2m[i])+0.5))

# send hour-forecast to OH
openhab = openHAB(url_oh)
Items = openhab.fetch_all_items()
for step in range(forecasts_h):
    index_step = index_last_interval_start + interval_hours*step
    time_hour = ((dt_last_interval_start_local.hour + interval_hours*step) % 24)
#    time_lead_zero = "%02d" % (time_hour,)
#    time_str = time_lead_zero
    if (time_hour >= 21) or (time_hour < 6):
        day_night = "Nacht"
        weather_code = code_night(int(Weather_1h[index_step]))
    else:
        day_night = "Tag"
        weather_code = code_day(int(Weather_1h[index_step]))
    send_oh('DWD_Vorhersage_h_Zeit_'+str(step),str(time_hour))
    send_oh('DWD_Vorhersage_h_TagNacht_'+str(step),day_night)
    send_oh('DWD_Vorhersage_h_Icon_'+str(step),folder_icons+weather_code+".png")
    send_oh('DWD_Vorhersage_h_Temp_'+str(step),Temp_2m,index_step)
    send_oh('DWD_Vorhersage_h_Taupunkt_'+str(step),DewPoint_2m,index_step)
    send_oh('DWD_Vorhersage_h_Luftfeuchtigkeit_'+str(step),Rel_Humidity,index_step)
    send_oh('DWD_Vorhersage_h_Regen_'+str(step),sum(Precipitation_1h[index_step+1:index_step+1+interval_hours])) # +1 because values are for past hour
    send_oh('DWD_Vorhersage_h_Regenwahrscheinlichkeit_'+str(step),max(Prob_Precip_1h[index_step+1:index_step+1+interval_hours]))
    send_oh('DWD_Vorhersage_h_Wind_'+str(step),3.6*max(Wind_Speed[index_step+1:index_step+1+interval_hours]))
    send_oh('DWD_Vorhersage_h_maxWind_'+str(step),3.6*max(Wind_Speed_max[index_step+1:index_step+1+interval_hours]))
send_oh('DWD_Vorhersage_h_Temp_max',max(Temp_2m[index_last_interval_start:index_last_interval_start+interval_hours*forecasts_h:interval_hours]))
send_oh('DWD_Vorhersage_h_Temp_min',min(Temp_2m[index_last_interval_start:index_last_interval_start+interval_hours*forecasts_h:interval_hours]))

# send daily forecasts to OH
for day in range(2,forecasts_d):
    day_name = (dt_today_local + datetime.timedelta(days=day)).strftime('%A')
    day_name_translated = translate_weekday(day_name)
    send_oh('DWD_Vorhersage_d_Tag_'+str(day),day_name_translated)
for day in range(forecasts_d):
    send_oh('DWD_Vorhersage_d_Tempmax_'+str(day),Temp_max_12h,index_tomorrow_utc-6+24*day)
    send_oh('DWD_Vorhersage_d_Tempmin_'+str(day),Temp_min_12h,index_tomorrow_utc+6+24*day)
    send_oh('DWD_Vorhersage_d_Regen_'+str(day),Precipitation_24h,index_tomorrow_utc+6+24*day)
    send_oh('DWD_Vorhersage_d_Regenwahrscheinlichkeit_'+str(day),Prob_Precip_24h,index_tomorrow_utc+6+24*day)
    send_oh('DWD_Vorhersage_d_Wolken_'+str(day),0) # not used - should be deleted later
    send_oh('DWD_Vorhersage_d_Sonnenstunden_'+str(day),[x / (60*60) for x in Sunshine_24h],index_tomorrow_utc+6+24*day)
    send_oh('DWD_Vorhersage_d_SonnenstundenProzent_'+str(day),RelSunshine_24h,index_tomorrow_utc+6+24*day)
    try:
        weather_code = code_day(int(Weather_24h[index_tomorrow_utc-6+24*day]))
        send_oh('DWD_Vorhersage_d_Icon_'+str(day),folder_icons+weather_code+".png")
    except Exception as e:
        print(e)
        print("problematic index is "+str(index_tomorrow_utc-6+24*day))
        pass
send_oh('DWD_Vorhersage_d_Tempmax_max',nan_max(Temp_max_12h[:index_tomorrow_utc-6+24*forecasts_d]))
send_oh('DWD_Vorhersage_d_Tempmin_min',nan_min(Temp_min_12h[:index_tomorrow_utc+6+24*forecasts_d]))
