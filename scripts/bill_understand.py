import boto3
import requests
from bs4 import BeautifulSoup
from botocore.exceptions import ClientError
import os
import time

BILL_HISTORY_URL = "https://capitol.texas.gov/BillLookup/History.aspx?LegSess=89R&Bill={}"
BILL_TEXT_URL = "https://capitol.texas.gov/BillLookup/Text.aspx?LegSess=89R&Bill={}"
TLO_BASE_URL = "https://capitol.texas.gov"

POLL_INTERVAL = 5  # Time in seconds between each poll

CLIENT = boto3.client("bedrock-runtime", region_name="us-west-2")
MODEL_ID = "anthropic.claude-3-5-sonnet-20241022-v2:0"

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

def lookup_bill_info(bill_number, url=BILL_HISTORY_URL):
    populated_url = url.format(bill_number)
    soup = fetch_and_parse(populated_url)
    caption = soup.find('td', id='cellCaptionText').text.strip()
    authors = soup.find('td', id='cellAuthors').text.strip().replace(' |', ',')  # Not to mess with MD table
    last_action = soup.find('td', id='cellLastAction').text.strip()
    print("Caption: {}\nAuthors: {}\nLast Action: {}\n".format(caption, authors, last_action))
    return (caption, authors, last_action)


def lookup_bill_text(bill_number, url=BILL_TEXT_URL):
    populated_url = url.format(bill_number)
    soup = fetch_and_parse(populated_url)
    links = soup.find_all("a", href=True)
    htm_links = []
    for link in links:
        if link["href"].endswith(".htm"):
            htm_links.append(TLO_BASE_URL + link["href"])

    # Assume the last one is the useful one
    # Can be an issue later as bill proceeds
    bill_text_url = htm_links[-1]

    return requests.get(bill_text_url).text

def understand_bill(bill_text):
    prompt = f"""
    You are a legal expert specialized in analyzing the potential impacts of legislature bills, specifically those impacts to immigrants from certain nations or countries.
    Please provide a summary of the bill in less than 80 words.

    Requirement:
    Be explicit if the Chinese immigrants are impacted.
    No need to include the date when the law become effective.
    The summary should discuss the potential effect of the law to any Chinese in the US.

    Please also provide a Chinese translation for the summary.

    Finally, list the most possible 3 committees this bill will be sent to.

    The bill text is as follows:
    {bill_text}
    """
    # Start a conversation with the user message.
    conversation = [
        {
            "role": "user",
            "content": [{"text": prompt}],
        }
    ]

    try:
        # Send the message to the model, using a basic inference configuration.
        response = CLIENT.converse(
            modelId=MODEL_ID,
            messages=conversation,
            inferenceConfig={"maxTokens": 512, "temperature": 0.5, "topP": 0.9},
        )

        # Extract and print the response text.
        response_text = response["output"]["message"]["content"][0]["text"]
        print(f"Response: {response_text}\n")
        return response_text

    except (ClientError, Exception) as e:
        print(f"ERROR: Can't invoke '{MODEL_ID}'. Reason: {e}")
        exit(1)

def update_bills_table(bills, url):
    with open("bills_table.md", "w") as f:
       f.write("|Bill Number|Summary|Caption|Authors|Last Actiond|\n")
       f.write("|-|-|-|-|-|\n")
       for bill in bills:
           bill_url = url.format(bill)
           caption, authors, last_action = lookup_bill_info(bill)
           bill_text = lookup_bill_text(bill)
           undersanding = understand_bill(bill_text).replace("\n", "<br>")
           f.write("|[{}]({})|{}|{}|{}|{}|\n".format(bill, bill_url, undersanding, caption, authors, last_action))
           time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    print("Collecting bills to understand...")
    if not os.path.isfile("bills_to_understand.txt"):
        raise Error("bills_to_understand.txt not found")
    else:
        with open('bills_to_understand.txt') as f:
            bills = f.read().splitlines()
            bills.sort()
    print("Understanding bills ...")
    update_bills_table(bills, BILL_HISTORY_URL)
