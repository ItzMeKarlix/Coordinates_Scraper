import requests
import csv
import time
import os

def get_coordinates(search_query):
    """Fetches coordinates from OpenStreetMap Nominatim API."""
    url = "https://nominatim.openstreetmap.org/search"
    
    # We add parameters to improve search accuracy for Philippine barangays
    params = {
        'q': search_query,
        'format': 'json',
        'addressdetails': 1,
        'extratags': 1,
        'namedetails': 1,
        'countrycodes': 'ph',
        'limit': 15  # Fetch more results to strictly find the barangay
    }
    
    # REQUIRED BY OSM: You must identify your application or you will be blocked!
    headers = {
        'User-Agent': 'CoordinatesBot/1.0 (name@insert_email_here.com)'  # Replace with your contact info
    }
    
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        if data:
            best_match = None
            
            # Step 1: Scan exactly for what OpenStreetMap considers a Barangay in the Philippines
            # (place=quarter OR boundary=administrative with admin_level=10 / admin_type:PH=barangay)
            for item in data:
                item_class = item.get('class', '')
                item_type = item.get('type', '')
                extratags = item.get('extratags') or {}
                
                is_barangay = False
                if item_class == 'place' and item_type == 'quarter':
                    is_barangay = True
                elif item_class == 'boundary' and item_type == 'administrative':
                    if extratags.get('admin_level') == '10' or extratags.get('admin_type:PH') == 'barangay':
                        is_barangay = True
                elif extratags.get('admin_type:PH') == 'barangay':
                    is_barangay = True
                    
                if is_barangay:
                    best_match = item
                    break
            
            # Step 2: Fallback if strictly marked barangay isn't found, try other place types
            if not best_match:
                for item in data:
                    if item.get('class') == 'place' and item.get('type') in ['village', 'suburb', 'neighbourhood']:
                        best_match = item
                        break
            
            # Step 3: If still no good match, take the top result.
            if not best_match:
                best_match = data[0]

            # Construct output details
            display_name = best_match.get('display_name', '')
            extratags = best_match.get('extratags') or {}
            # Include alt_name or name if available in extratags to verify
            official_name = best_match.get('name', '')
            alt_name = extratags.get('alt_name', '')
            
            if alt_name:
                display_name = f"{official_name} (Alt: {alt_name}) - {display_name}"

            # Get the type of the matched place (e.g., 'quarter', 'suburb', 'administrative')
            place_type = best_match.get('type', 'Unknown')

            return best_match['lat'], best_match['lon'], display_name, place_type
        else:
            return "Not Found", "Not Found", "Not Found", "Not Found"
    except Exception as e:
        print(f"Error fetching data: {e}")
        return "Error", "Error", str(e), "Error"

def main():
    print("--- OpenStreetMap Coordinates Scraper ---")
    
    print("\nHow would you like to input the locations?")
    print("1. Type locations manually")
    print("2. Read automatically from list.txt")
    input_method = input("Enter choice (1 or 2): ")
    
    locations = []
    
    if input_method == '1':
        print("\nEnter locations one by one (e.g., Punta I, Tanza, Cavite). Type 'DONE' when finished.")
        while True:
            loc = input("Location: ")
            if loc.upper() == 'DONE':
                break
            if loc.strip():
                locations.append(loc.strip())
                
    elif input_method == '2':
        filename = "list.txt"
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                # Replace tabs with spaces and remove empty lines
                locations = [line.strip().replace('\t', ' ') for line in f if line.strip()]
        else:
            print(f"Error: {filename} not found. Please create {filename} and add your locations line by line.")
            return
    else:
        print("Invalid choice. Exiting.")
        return

    if not locations:
        print("No locations to process. Exiting.")
        return

    # Prepare CSV output
    output_file = "coordinates_results.csv"
    
    print(f"\nStarting to fetch coordinates for {len(locations)} location(s)...")
    print("NOTE: Added a 1.5 second delay between requests to prevent OpenStreetMap rate-limiting.")
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        # Write headers, including the OSM Type
        writer.writerow(['Original Input', 'Latitude', 'Longitude', 'OSM Display Name', 'OSM Type'])
        
        for loc in locations:
            print(f"Fetching {loc}...")
            
            # Clean up the input. OpenStreetMap often fails if you include words like "Quarter" or "Barangay" 
            # at the exact start of a comma-separated search query.
            query = loc
            if query.lower().startswith('quarter,'):
                query = query[8:].strip()
            elif query.lower().startswith('quarter '):
                query = query[8:].strip()
            elif query.lower().startswith('barangay,'):
                query = query[9:].strip()
            elif query.lower().startswith('barangay '):
                query = query[9:].strip()

            # Fix common Roman numeral vs Arabic numeral issues for Amaya/Daang Amaya etc.
            # OSM is sometimes strict, so passing the base name like "Amaya 1, Tanza" will let our script's
            # enhanced matching logic find the Roman numeral version automatically.

            # Automatically append Philippines to make search more accurate if not present
            if "Philippines" not in query:
                query = f"{query}, Philippines"
            
            lat, lon, display_name, place_type = get_coordinates(query)
            
            writer.writerow([loc, lat, lon, display_name, place_type])
            
            if lat not in ["Not Found", "Error"]:
                print(f"  Found: [{place_type}] {lat}, {lon} -> {display_name}")
            else:
                print("  Coordinates not found.")
                
            # RATE LIMITING: Essential to avoid getting banned by OSM
            time.sleep(1.5) 
            
    print(f"\nDone! Results saved successfully to {output_file}")

if __name__ == "__main__":
    main()
