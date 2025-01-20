import time
import re
import requests
from bs4 import BeautifulSoup

# Configuration
URL = "https://capitol.texas.gov/Search/TextSearchResults.aspx?CP={}&shCaption=True&shExcerpt=True&billSort=True&LegSess=89R&House=True&Senate=True&TypeB=True&TypeR=False&TypeJR=True&TypeCR=False&VerInt=True&VerHCR=True&VerEng=True&VerSCR=True&VerEnr=True&DocTypeB=True&DocTypeFN=False&DocTypeBA=False&DocTypeAM=False&Srch=simple&All=&Any=china%2c+chinese%2c+alien%2c+foreign&Exact=&Exclude=&Custom="
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

def extract_key_info(soup, tag, id_pattern):
    """Extract key information from the parsed HTML."""
    elements = soup.find_all(tag, id=id_pattern)
    return [element['id'] for element in elements]

def poll_url(url, tag, css_class=None, interval=60):
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


if __name__ == "__main__":
    print("Starting URL Poller...")
    poll_url(URL, EXTRACTION_TAG, ID_PATTERN, POLL_INTERVAL)