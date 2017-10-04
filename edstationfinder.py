import time
import os.path
import requests
import requests_cache
import sqlite3
import json
from timeit import default_timer as timer

verbose = False #Verbose output for debugging.
padSize = 'L' #Pad size for matches.
lyRange = 14 #Maximum sitance between systems.
minDistance = 30000 #Minimum station distance from star.
maxDistance = 999999999 #Maximum station distance from star.

requests_cache.install_cache() #Cache responses from EDSM to greatly speed up subsequent runs.

stationRange = range(minDistance,maxDistance)


def getStationSystem(stationID): #Returns a system name from a system ID
    c.execute('''SELECT system.name 
                FROM system,station 
                WHERE station.system=system.id 
                AND station.id=?''', [stationID] )
    systemName = dict(c.fetchone()).get('name')
    if verbose:
        print('Returning system name: %s' % (systemName))
    return systemName
    
def getSystemID(systemName): #Returns a system ID from a system name
    systemName = str(systemName)
    c.execute('''SELECT system.id 
                FROM system
                WHERE system.name=?''', [systemName] )
    systemID = dict(c.fetchone()).get('id')
    if verbose:
        print('Returning %s ID: %d' % (systemName, systemID))
    return systemID
    
def getSystemName(systemID): #Returns a system name from a system ID
    c.execute('''SELECT system.name
                FROM system
                WHERE system.id=?''', [systemID] )
    systemName = dict(c.fetchone()).get('name')
    if verbose:
        print('Returning name of system with ID %d: %s' % (systemID, systemName))
    return systemName

def getSystemPopulation(stationID): #Returns the population of a system containing a specific sation by ID
    c.execute('''SELECT system.population 
                FROM system,station 
                WHERE station.system=system.id 
                AND station.id=?''', [stationID] )
    systemPopulation = c.fetchone()[0]
    if verbose:
        print('Returning population of %s: %d' % (getStationSystem(stationID), systemPopulation))
    return systemPopulation

def getStationCount(systemID): #Returns the number of stations in a system using the system ID
    c.execute('''SELECT COUNT(station.system) as stationCount 
                FROM station 
                LEFT OUTER JOIN system 
                ON (system.id = station.system) 
                WHERE system.id=? and station.pad <> "None"''', [systemID] )
    stationCount = c.fetchone()[0]
    if verbose:
        print('Returning number of stations in %s: %d' % (getSystemName(systemID), stationCount))
    return stationCount

def listSystemStations(systemID): #List the stations in a system based on the variables at the beginning of the script
    stationList = []
    c.execute('''SELECT station.name as stationname, station.distance, station.allegiance, station.pad
                FROM station 
                LEFT OUTER JOIN system 
                ON (system.id = station.system) 
                WHERE system.id=? and station.pad <> "None"''', [systemID] )
    systemStations = c.fetchall()
    for station in systemStations:
        stationList.append(dict(station))
    if verbose:
        print('Returning list of stations in %s:\n%s' % (getSystemName(systemID), str(stationList)))
    return stationList

def findStations(minDistance, maxDistance, padSize): #Find an initial list of systems that match station criteria
    stationList = []
    criteria = [minDistance, maxDistance, padSize]
    c.execute('''SELECT system.id as systemID, system.name as systemname, station.id as stationID, station.name as stationname, station.distance, station.pad
                FROM station 
                LEFT OUTER JOIN system 
                ON (system.id = station.system) 
                WHERE station.distance > ? and station.distance < ? and station.pad=?''', criteria)
    stations = c.fetchall()
    for station in stations:
        stationList.append(dict(station))
    if verbose:
        print('Returning list of stations %d-%d from start with a %s landing pad:\n%s' % (minDistance, maxDistance, padSize, stationList))
    return stationList

def findNearbyStations(systemName, range): #Connect to EDSM to find all systems within specified ly range of another system.
    global start
    edsmapi = 'https://www.edsm.net/api-v1/sphere-systems'
    payload = {'systemName': systemName, 'radius': range }
    try:
        start
    except:
        timeout = 0
    else:
        end = timer()
        offset = end - start
        timeout = 10 - offset #Adjust timeout by changing 10. MOVE TO VARIABLE IN BETTER PLACE
        if timeout < 0:
            timeout = 0
        if verbose:
            print('%s seconds since last API call' % (str(round(offset, 2))))
    session = requests_cache.CachedSession() #Cache responses from EDSM for faster subsequent runs.
    session.hooks = {'response': make_throttle_hook(timeout)}
    response = session.get(edsmapi, params=payload, stream=True)
    if response.from_cache == False:
        start = timer()
    if response.status_code == 200:
        nearbySystems = response.json()
        if verbose:
            if response.from_cache:
                print('API response exists in cache')
            else:
                print('Querying EDSM API')
            print('Returning list of stations within %dly of %s:\n%s' % (range, systemName, str(nearbySystems)))
        return nearbySystems
    elif response.status.code == 429:
        print('Too many requests. EDSM API stopped responding. Please adjust rate limiter and try again later.')
        raise SystemExit
    else:
        raise SystemExit('Unknow error connecting to EDSM\nEDSM response status: %s' % (str(response.status_code)))

def isSystemHit(systemID): #Determine if a system by ID matches search criteria.
    if getStationCount(systemID) == 1:
        distance = listSystemStations(systemID)[0].get('distance')
        stationName = listSystemStations(systemID)[0].get('stationname')
        pad = listSystemStations(systemID)[0].get('pad')
        if verbose:
            print('Checking if %s(%d/%s) meets distance pad criteria' % (stationName, distance, pad))
        if distance in stationRange and pad == padSize:
            if verbose:
                print('%s is within stationRange of %d-%d(%d) with a %s pad' % (stationName, minDistance, maxDistance, distance, padSize))
            return True

def compareStations(): 
    '''
    Loops on results from initial findStations() search.
    Sends each system to EDSM asking for a list of station within the specified radius (lyRange).
    Loops on response from EDSM checking if stations meet criteria and are not duplicates.
    If station matches search parameters, write origin and destination system names to results.txt log.
    '''
    stations = findStations(minDistance, maxDistance, padSize)
    for station in stations:
        originSystemID = station.get('systemID')
        originSystemName = station.get('systemname')
        originStationDistance = station.get('distance')
        print('Comparing %s to nearby systems' % (originSystemName))
        nearbySystems = findNearbyStations(originSystemName, lyRange)
        for system in nearbySystems:
            destSystemName = system.get('name')
            destSystemDistance = system.get('distance')
            try:
                destSystemID = getSystemID(destSystemName)
                if verbose:
                    print('Comparing %s to %s' % (originSystemName, destSystemName))
                if isSystemHit(destSystemID) and duplicate(originSystemName, destSystemName) == False:
                    destStationDistance = listSystemStations(destSystemID)[0].get('distance')
                    print('\n!HIT: %s(%dls) to %s(%dls) - (%dly)\n' % (originSystemName, originStationDistance, destSystemName, destStationDistance, destSystemDistance))
                    with open('results.txt', 'a') as results:
                        results.write('%s(%dls) to %s(%dls) - (%dly)\r\n' % (originSystemName, originStationDistance, destSystemName, destStationDistance, destSystemDistance))
                    results.close()
            except TypeError:
                pass

def duplicate(originSystemName, destSystemName): #Check if origin and destination are same or exist in results.txt already in reverse order.
    if originSystemName == destSystemName:
        if verbose:
            print('!DUPLICATE: %s and %s are the same' % (originSystemName, destSystemName))
        return True
    with open('results.txt', 'a+') as results:
        for hit in results:
            if originSystemName in hit and destSystemName in hit:
                if verbose:
                    print('!DUPLICATE: %s and %s already exist in list' % (originSystemName, destSystemName))
                results.close()
                return True
    if verbose:
        print('No duplicates found for %s and %s' % (originSystemName, destSystemName))
    return False
    
def make_throttle_hook(timeout):
    '''
    Rate limiter:
    Hooks into Requests.
    If < 10 seconds have passes since the last non-cached API request,
    sleeps for the API rate limit timer minus the time spent executing the rest of the script.
    '''
    def hook(response, *args, **kwargs):
        if not getattr( response, 'from_cache', False):
            if timeout != 0:
                print('API RATE LIMIT: Sleeping for %s seconds' % (str(round(timeout, 2))))
            time.sleep(timeout)
        return response
    return hook
    
def primeDatabase():
    '''
    If database of systems and stations does not exist:
    - Gets system and station data from EDDB in JSON lines format.
    - Split JSON lines file into list containing JSON info for each system and station.
    - Create database file and connection then initialize schema.
    - Iterate over systems, then stations, writing to respective database tables.
    '''
    print('Priming database with system and station data from EDDB')
    
    if verbose:
        print('Retreiving jsonl-formatted populated system and station data from EDDB')
    systemsUrl = 'https://eddb.io/archive/v5/systems_populated.jsonl'
    stationsUrl = 'https://eddb.io/archive/v5/stations.jsonl'

    systemsResponse = requests.get(systemsUrl, stream=True).iter_lines(decode_unicode=True)
    stationsResponse = requests.get(stationsUrl, stream=True).iter_lines(decode_unicode=True)

    db = sqlite3.connect('db.sqlite')
    c = db.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS system(id INTEGER PRIMARY KEY, edsmid INTEGER, name TEXT, allegiance TEXT, population INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS station(id INTEGER PRIMARY KEY, name TEXT, system INTEGER, pad TEXT, distance INTEGER, allegiance TEXT, FOREIGN KEY(system) REFERENCES system(id))''')

    systemdatalist = []
    stationdatalist = []

    for item in systemsResponse:
        systemjson = json.loads(item)
        id = systemjson['id']
        edsmid = systemjson['edsm_id']
        name = systemjson['name']
        allegiance = systemjson['allegiance']
        population = systemjson['population']
        systemdata = [id, edsmid, name, allegiance, population]
        if verbose:
            print('Preparing to write %s to database' % (name))
        systemdatalist.append(systemdata)

    c.executemany('INSERT INTO system VALUES (?,?,?,?,?)', systemdatalist)
    if verbose:
        print('Writing populated systems to database')
    db.commit()
    print('Finished Stations')
    systemdatalist = [] #Clear list. Probably not necessary but fuck it.

    for item in stationsResponse:
        stationjson = json.loads(item)
        id = stationjson['id']
        name = stationjson['name']
        system = stationjson['system_id']
        pad = stationjson['max_landing_pad_size']
        distance = stationjson['distance_to_star']
        allegiance = stationjson['allegiance']
        stationdata = [id, name, system, pad, distance, allegiance]
        if verbose:
            print('Preparing to write %s to database' % (name))
        stationdatalist.append(stationdata)

    c.executemany('INSERT INTO station VALUES (?,?,?,?,?,?)', stationdatalist)
    db.commit()
    print('Finished Stations')
    db.close()
    stationdatalist = [] #Clear list. Probably not necessary but fuck it.

if os.path.exists('db.sqlite') == False: # If database file does not exist, create and prime the database with data.
    primeDatabase()

db = sqlite3.connect('db.sqlite') #Initial database connection.
db.row_factory = sqlite3.Row
c = db.cursor()

compareStations() #Do it.