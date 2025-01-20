import time
import re
import requests
import os.path
from bs4 import BeautifulSoup

# Configuration
BILL_SCAN_URL = "https://capitol.texas.gov/Search/TextSearchResults.aspx?CP={}&shCaption=True&shExcerpt=True&billSort=True&LegSess=89R&House=True&Senate=True&TypeB=True&TypeR=False&TypeJR=True&TypeCR=False&VerInt=True&VerHCR=True&VerEng=True&VerSCR=True&VerEnr=True&DocTypeB=True&DocTypeFN=False&DocTypeBA=False&DocTypeAM=False&Srch=simple&All=&Any=china%2c+chinese%2c+alien%2c+foreign&Exact=&Exclude=&Custom="
BILL_SEARCH_URL = "https://capitol.texas.gov/BillLookup/History.aspx?LegSess=89R&Bill={}"

POLL_INTERVAL = 2  # Time in seconds between each poll
EXTRACTION_TAG = "a"  # HTML tag to extract
ID_PATTERN = re.compile(r'^\d{2}R-(HB|SB)\d+$')  # Matches IDs like 89R-HB994, 89R-HB1017


def fetch_and_parse(url):
    """Fetch the content of the URL and parse it with BeautifulSoup."""
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise HTTPError for bad responses
        with open("response.txt", "w") as response_file:
            response_file.write(response.text)
        return BeautifulSoup(response.text, "html.parser")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching the URL: {e}")
        return None

def extract_key_info(soup, tag, id_pattern=None):
    """Extract key information from the parsed HTML."""
    if id_pattern:
        elements = soup.find_all(tag, id=id_pattern)
    return [element['id'] for element in elements]

def scan_bills(url, tag, css_class=None, interval=60):
    page_num = 1
    bills = []
    while True: 
        populated_url = url.format(page_num)
        print(f"Polling {populated_url}...")
        soup = fetch_and_parse(populated_url)
        info = extract_key_info(soup, tag, css_class)
        if info:
            print("Extracted Information:")
            for item in info:
                print(f"- {item}")
                bills.append(item.split("-")[1])
            page_num += 1
        else:
            print("No information found.")
            break
        print(f"Waiting for {interval} seconds...\n")
        time.sleep(interval)
    print("Bills: ", bills)
    with open("bills_scanned.txt", "w") as bills_scanned_file:
        for bill in bills:
            bills_scanned_file.write(bill + '\n')
    return bills

def lookup_bill(url, bill_number): 
    populated_url = url.format(bill_number)
    soup = fetch_and_parse(populated_url)
    caption = soup.find('td', id='cellCaptionText').text.strip()
    authors = soup.find('td', id='cellAuthors').text.strip().replace(' |', ',')  # Not to mess with MD table 
    last_action = soup.find('td', id='cellLastAction').text.strip()
    print("Caption: {}\nAuthors: {}\nLast Action: {}\n".format(caption, authors, last_action))
    return (caption, authors, last_action)

def generate_bills_table(bills, url):
    with open("bills_table.md", "w") as f:
       f.write("|Bill Number|Caption|Authors|Last Action|\n")
       f.write("|-|-|-|-|\n") 
       for bill in bills:
           bill_url = url.format(bill)
           caption, authors, last_action = lookup_bill(BILL_SEARCH_URL, bill)
           f.write("|[{}]({})|{}|{}|{}|\n".format(bill, bill_url, caption, authors, last_action))
           time.sleep(POLL_INTERVAL)



if __name__ == "__main__":
    print("Starting bills search...")
    if not os.path.isfile("bills_scanned.txt"):
        bills = scan_bills(BILL_SCAN_URL, EXTRACTION_TAG, ID_PATTERN, POLL_INTERVAL)
    else:
        with open('bills_scanned.txt') as f:
            bills = f.read().splitlines()
    print("Looking up bills info...")
    generate_bills_table(bills, BILL_SEARCH_URL)
    
