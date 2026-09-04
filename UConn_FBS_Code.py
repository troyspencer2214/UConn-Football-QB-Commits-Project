import requests #will allow us to request information from a website
import csv #allows us to create a .csv file with the information
import time
from datetime import datetime

from selenium import webdriver #allows us to open the recruit interest pages in chrome
from selenium.webdriver.common.by import By #allows us to search through the chrome page
from selenium.webdriver.support.ui import WebDriverWait #allows us to wait for information to load
from selenium.webdriver.support import expected_conditions as EC #allows us to tell selenium what information we are waiting for


YEARS = [2024, 2025, 2026] #Years that we are doing

ITEMS_PER_PAGE = 50 #Will Be Useful later to determine the length of pages


#Allows us to seem more human when requesting from the site
normal_headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/152.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


#naming our eventual csv file
output_file = "uconn_qb_recruits_2024_2026.csv"


#Our Columns dervied from the information that can be pulled
fieldnames = [
    "QB",
    "CLASS",
    "247 RATINGS",
    "STARS",
    "HEIGHT",
    "WEIGHT",
    "POSITION",
    "STATE",
    "HOMETOWN",
    "HIGH SCHOOL",
    "COMMITTED DATE",
    "POSITION RANK",
    "NATIONAL RANK",
    "STATE RANK",
    "COMMITTED SCHOOL ID",
    "COMMITTED SCHOOL",
    "RECRUIT STATUS",
    "PLAYER URL",
]


#formats the date's and time properly because it wasn't initally
def clean_commit_date(date_string):

    if not date_string:
        return ""

    try:

        date_object = datetime.strptime(
            date_string,
            "%m/%d/%Y %I:%M:%S %p"
        )

        return date_object.strftime(
            "%m/%d/%Y"
        )

    except ValueError:

        return date_string


#this function uses chrome to find the school that the quarterback committed to
def get_committed_school(
    driver,
    recruit_interests_url
):

    #if there isn't a recruit interest page we can't find the school
    if not recruit_interests_url:

        return ""


    #opening the player's recruit interests page
    try:

        driver.get(
            recruit_interests_url
        )


    #if chrome can't open the page we return blank so the rest of the program can continue
    except Exception as e:

        print(
            "Could not open recruit interests page:"
        )

        print(
            recruit_interests_url
        )

        print(e)

        return ""


    #waiting for the list of schools to appear on the page
    try:

        wait = WebDriverWait(
            driver,
            15
        )

        wait.until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    "ul.recruit-interest-index_lst"
                )
            )
        )


    #if the recruiting list never appears we return blank
    except Exception:

        print(
            "Recruit interest list did not load."
        )

        return ""


    #getting every school row from the recruit interest list
    school_rows = driver.find_elements(
        By.CSS_SELECTOR,
        "ul.recruit-interest-index_lst > li"
    )


    #looking through every school that recruited the player
    for row in school_rows:

        try:

            #gets the section that contains the school name and recruiting status
            first_block = row.find_element(
                By.CSS_SELECTOR,
                "div.first_blk"
            )


            #gets the first link which we found is the actual school name
            school = first_block.find_element(
                By.CSS_SELECTOR,
                "a"
            ).text.strip()


            #trying to find the recruiting status
            try:

                status = first_block.find_element(
                    By.CSS_SELECTOR,
                    "span.status"
                ).text.strip()


            #if there isn't a status this isn't the school they committed to
            except:

                status = ""


            #only keeping the school if the player enrolled, signed, or committed there
            if (
                "Enrolled" in status
                or "Signed" in status
                or "Committed" in status
            ):

                return school


        #if there is a strange row we skip it and move to the next school
        except:

            continue


    #if we checked every school and couldn't find the committed one we return blank
    return ""


#creates a session which we can loop
session = requests.Session()


#creates an empty list where we will put all the qb names then run a for loop using it to put the information into the csv
all_qbs = []


#creates a dictionary that will remember which school belongs to each 247 school id
school_lookup = {}


#opening chrome once so we don't have to open a new browser for every quarterback
print(
    "OPENING CHROME"
)


driver = webdriver.Chrome()


#for loop to make sure we do all years, as well as a printing process to let whoever runs it to know that it's working
for year in YEARS:

    print("\n")
    print(f"STARTING {year}")


    #open's the url with whatever the year of the for loop is
    normal_url = (
        f"https://247sports.com/"
        f"season/{year}-football/commits/"
        f"?PositionGroup=1"
    )


    #we are using the try function to get the data instead of Beautiful Soup, because the site is encoded with python that makes it very easy to use the get function
    try:

        normal_response = session.get(
            normal_url,
            headers=normal_headers,
            timeout=30
        )


    #this is a debugging feature that allows for us to see when the page can't open, then we skip that year.
    except requests.exceptions.RequestException as e:

        print(
            f"Could not open normal "
            f"{year} page:"
        )

        print(e)

        continue


    print(
        "Normal page status:",
        normal_response.status_code
    )


    if normal_response.status_code != 200:

        print(
            f"Skipping {year} because "
            f"the normal page failed."
        )

        continue


    #In order to find more than just the page limited 50 names, we had to actually get into the original file that the site pulls from, so this is just creating our user for that site
    json_headers = {
        "User-Agent":
            normal_headers["User-Agent"],

        "Accept":
            "application/json, "
            "text/javascript, */*; q=0.01",

        "Accept-Language":
            "en-US,en;q=0.9",

        "Referer":
            normal_url,

        "X-Requested-With":
            "XMLHttpRequest",
    }


    page = 1
    year_qbs = 0
    year_recruits_checked = 0


    #this loop is doing the same thing as above, and it's just letting us know if the requested information has been accepted
    while True:

        json_url = (
            f"https://247sports.com/"
            f"Season/{year}-Football/"
            f"Recruits.json"
            f"?Items={ITEMS_PER_PAGE}"
            f"&Page={page}"
        )


        print(
            f"\n{year} | Requesting page "
            f"{page}..."
        )


        try:

            response = session.get(
                json_url,
                headers=json_headers,
                timeout=30
            )


        except requests.exceptions.RequestException as e:

            print(
                "Request failed:"
            )

            print(e)

            break


        print(
            "Status:",
            response.status_code
        )


        if response.status_code != 200:

            print(
                "Stopping this year "
                "because request failed."
            )

            break


        #incase of error
        try:

            data = response.json()


        except ValueError:

            print(
                "Response was not valid JSON."
            )

            break


        print(
            "Records returned:",
            len(data)
        )


        #Checking if there is nothing left so we can stop loop
        if len(data) == 0:

            print(
                "No more recruits."
            )

            break


        year_recruits_checked += len(data)


        #getting players
        for item in data:

            player = item.get(
                "Player"
            )


            if not player:

                continue


            #getting positions
            position_data = player.get(
                "PrimaryPlayerPosition"
            )


            if not position_data:

                continue


            position = position_data.get(
                "Abbreviation"
            )


            #only keeping quarterbacks
            if position != "QB":

                continue


            #only committed players
            committed_school_id = item.get(
                "CommittedInstitution"
            )


            if not committed_school_id:

                continue


            #names
            name = player.get(
                "FullName",
                ""
            )


            #hometowns
            hometown_data = player.get(
                "Hometown"
            ) or {}


            hometown = hometown_data.get(
                "City",
                ""
            )


            state = hometown_data.get(
                "State",
                ""
            )


            #highschool
            high_school_data = player.get(
                "PlayerHighSchool"
            ) or {}


            high_school = high_school_data.get(
                "Name",
                ""
            )


            #commit_date
            commit_date = clean_commit_date(
                item.get(
                    "AnnouncementDate"
                )
            )


            #recruit status
            recruit_status = item.get(
                "HighestRecruitInterestEventType",
                ""
            )


            #getting the url where all of the recruit's school interests are stored
            recruit_interests_url = item.get(
                "RecruitInterestsUrl",
                ""
            )


            #checking if we have already figured out what school this id belongs to
            if committed_school_id in school_lookup:

                committed_school = school_lookup[
                    committed_school_id
                ]


                print(
                    "SCHOOL ALREADY KNOWN:",
                    committed_school_id,
                    "=",
                    committed_school
                )


            #if we haven't seen the school id yet we use chrome to figure out the school
            else:

                print(
                    "Finding committed school for:",
                    name
                )


                committed_school = get_committed_school(
                    driver,
                    recruit_interests_url
                )


                #only saving the school if selenium actually found one
                if committed_school:

                    school_lookup[
                        committed_school_id
                    ] = committed_school


                print(
                    "COMMITTED SCHOOL:",
                    committed_school_id,
                    "=",
                    committed_school
                )


                #waiting briefly before opening another recruit page
                time.sleep(0.5)


            #building rows
            row = {
                "QB":
                    name,

                "CLASS":
                    item.get(
                        "Year",
                        year
                    ),

                "247 RATINGS":
                    player.get(
                        "Rating",
                        ""
                    ),

                "STARS":
                    player.get(
                        "StarRating",
                        ""
                    ),

                "HEIGHT":
                    player.get(
                        "Height",
                        ""
                    ),

                "WEIGHT":
                    player.get(
                        "Weight",
                        ""
                    ),

                "POSITION":
                    position,

                "STATE":
                    state,

                "HOMETOWN":
                    hometown,

                "HIGH SCHOOL":
                    high_school,

                "COMMITTED DATE":
                    commit_date,

                "POSITION RANK":
                    player.get(
                        "PositionRank",
                        ""
                    ),

                "NATIONAL RANK":
                    player.get(
                        "NationalRank",
                        ""
                    ),

                "STATE RANK":
                    player.get(
                        "StateRank",
                        ""
                    ),

                "COMMITTED SCHOOL ID":
                    committed_school_id,

                "COMMITTED SCHOOL":
                    committed_school,

                "RECRUIT STATUS":
                    recruit_status,

                "PLAYER URL":
                    player.get(
                        "Url",
                        ""
                    ),
            }


            all_qbs.append(
                row
            )

            year_qbs += 1


            print(
                "QB FOUND:",
                name,
                "| School:",
                committed_school,
                "| Rating:",
                player.get("Rating"),
                "| Rank:",
                player.get("PositionRank")
            )


        #loop continuation
        if len(data) < ITEMS_PER_PAGE:

            print(
                "\nReached final page."
            )

            break


        page += 1


        #To not get site banned
        time.sleep(1)


    #yearly summary
    print("\n")

    print(
        f"{year} recruits checked:",
        year_recruits_checked
    )

    print(
        f"{year} committed QBs found:",
        year_qbs
    )


#closing chrome after all three years are finished
print(
    "\nCLOSING CHROME"
)


driver.quit()


#creating the csv file
with open(
    output_file,
    "w",
    newline="",
    encoding="utf-8-sig"
) as csvfile:

    writer = csv.DictWriter(
        csvfile,
        fieldnames=fieldnames
    )

    writer.writeheader()

    writer.writerows(
        all_qbs
    )


#ending summary
print("\n")

print(
    "FINISHED"
)

print(
    "TOTAL COMMITTED QBs:",
    len(all_qbs)
)

print(
    "TOTAL DIFFERENT SCHOOLS FOUND:",
    len(school_lookup)
)

print(
    "CSV CREATED:",
    output_file
)