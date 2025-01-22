import time
import re
import requests
import os.path
from bs4 import BeautifulSoup
from utils import fetch_and_parse

# Configuration
BILL_SCAN_URL = "https://capitol.texas.gov/Search/TextSearchResults.aspx?CP={}&shCaption=True&shExcerpt=True&billSort=True&LegSess=89R&House=True&Senate=True&TypeB=True&TypeR=False&TypeJR=True&TypeCR=False&VerInt=True&VerHCR=True&VerEng=True&VerSCR=True&VerEnr=True&DocTypeB=True&DocTypeFN=False&DocTypeBA=False&DocTypeAM=False&Srch=simple&All=&Any=china%2c+chinese%2c+alien%2c+foreign&Exact=&Exclude=&Custom="
BILL_SEARCH_URL = "https://capitol.texas.gov/BillLookup/History.aspx?LegSess=89R&Bill={}"

POLL_INTERVAL = 2  # Time in seconds between each poll
EXTRACTION_TAG = "a"  # HTML tag to extract
ID_PATTERN = re.compile(r'^\d{2}R-(HB|SB)\d+$')  # Matches IDs like 89R-HB994, 89R-HB1017

def extract_key_info(soup, tag, id_pattern=ID_PATTERN):
    """Extract key information from the parsed HTML."""
    elements = soup.find_all(tag, id=id_pattern)
    return [element['id'] for element in elements]

def scan_bills(url, tag, interval=60):
    page_num = 1
    bills = []
    while True:
        populated_url = url.format(page_num)
        print(f"Polling {populated_url}...")
        soup = fetch_and_parse(populated_url)
        info = extract_key_info(soup, tag)
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

if __name__ == "__main__":
    print("Starting bills search...")
    if not os.path.isfile("bills_scanned.txt"):
        bills = scan_bills(BILL_SCAN_URL, EXTRACTION_TAG, POLL_INTERVAL)
    else:
        with open('bills_scanned.txt') as f:
            bills = f.read().splitlines()
    with open("bills_patch.txt") as f:
        bills_patch = f.read().splitlines()
    for bill in bills_patch:
        if bill not in bills:
            bills.append(bill)
            print(f"Added: {bill}")
    with open("bills_to_understand.txt", "w") as f:
        for bill in bills:
            f.write(bill + '\n')

