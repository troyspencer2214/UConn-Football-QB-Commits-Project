from bs4 import BeautifulSoup
import requests
import csv
import os
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

url2026 = "https://247sports.com/season/2026-football/commits/?PositionGroup=1"
url2025 = "https://247sports.com/season/2025-football/commits/?PositionGroup=1"
url2024 = "https://247sports.com/season/2024-football/commits/?PositionGroup=1"

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/152.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

scraping_site2026 = requests.get(url2026,headers=headers,timeout=20)

soup = BeautifulSoup(scraping_site2026.text, "html.parser")
commit_names = soup.find_all("a", class_="ri-page__name-link")
school_home_towns = soup.find_all("span", class_="meta")


file = open("UConn_Football_Project.csv", "w", newline="")
writer = csv.writer(file)

writer.writerow([
    "QB", "Class", "247 Rating", "Proximity to Home", "Duel Threat vs Pocket Passer", "Stars", "Ratings", "Height \(inches\)", "Weight \(lbs\)", "High School Rating", "High School Level", "State", "Home Town", "High School", "Injury Status", "Conference", "Committed School", "Committed Date", "Position Rank", "National Rank", "State Rank"
])

for name in commit_names:
    writer.writerow([name.text, "2026"])
file.close()

print(os.path.abspath("UConn_Football_Project.csv"))