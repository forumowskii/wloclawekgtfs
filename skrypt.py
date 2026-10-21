import os
import time
from google.transit import gtfs_realtime_pb2
from playwright.sync_api import sync_playwright

DESKTOP_URL = "http://its.wloclawek.eu/desktop/public-transport?show=all"

print("Pobieranie danych z ITS Włocławek w chmurze GitHub...")
api_responses = {}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    def handle_response(response):
        if "query?name=PublicTransport" in response.url:
            try:
                json_data = response.json()
                api_responses[response.url] = json_data
            except Exception:
                pass

    page.on("response", handle_response)
    page.goto(DESKTOP_URL, timeout=60000, wait_until="networkidle")
    time.sleep(6)
    browser.close()

target_url_key = None
for url in api_responses.keys():
    if "Vehicles.List" in url or "Trips.List" in url:
        target_url_key = url
        break

if target_url_key:
    data = api_responses[target_url_key]
    
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"
    feed.header.incrementality = gtfs_realtime_pb2.FeedHeader.FULL_DATASET
    feed.header.timestamp = int(time.time())
    
    items = data if isinstance(data, list) else data.get("result", [])
    count = 0
    
    for idx, item in enumerate(items):
        position = item.get("position", {})
        coords = position.get("coordinates", [])
        
        if len(coords) < 2:
            continue
            
        lon, lat = coords[0], coords[1]
        route_id = str(item.get("routeShortName", ""))
        trip_id = str(item.get("tripId", f"trip_{idx}"))
        vehicle_id = str(item.get("vehicleId", f"bus_{idx}"))
        deviation = item.get("deviation", 0)
        
        entity = feed.entity.add()
        entity.id = f"vehicle_{vehicle_id}_{idx}"
        entity.vehicle.trip.trip_id = trip_id
        entity.vehicle.trip.route_id = route_id
        entity.vehicle.vehicle.id = vehicle_id
        entity.vehicle.position.latitude = float(lat)
        entity.vehicle.position.longitude = float(lon)
        entity.vehicle.timestamp = int(time.time())
        
        if deviation is not None:
            tu_entity = feed.entity.add()
            tu_entity.id = f"tu_{vehicle_id}_{idx}"
            tu_entity.trip_update.trip.trip_id = trip_id
            tu_entity.trip_update.trip.route_id = route_id
            tu_entity.trip_update.vehicle.id = vehicle_id
            tu_entity.trip_update.delay = int(deviation)
            
        count += 1

    filename = "wloclawek_gtfs_rt.pb"
    with open(filename, "wb") as f:
        f.write(feed.SerializeToString())
    print(f"Sukces! Przetworzono pojazdów: {count}")
else:
    raise Exception("Nie złapano danych o pojazdach z API.")
