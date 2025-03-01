import requests
from bs4 import BeautifulSoup
from botocore.exceptions import ClientError
from botocore.config import Config
import os
import time
import datetime
import json
from utils import fetch_and_parse, extract_string_by_tag
from llm_utils import *

BILL_HISTORY_URL = "https://capitol.texas.gov/BillLookup/History.aspx?LegSess=89R&Bill={}"
BILL_TEXT_URL = "https://capitol.texas.gov/BillLookup/Text.aspx?LegSess=89R&Bill={}"
TLO_BASE_URL = "https://capitol.texas.gov"

POLL_INTERVAL = 10  # Time in seconds between each poll

def lookup_bill_info(bill_number, url=BILL_HISTORY_URL):
    try:
        populated_url = url.format(bill_number)
        soup = fetch_and_parse(populated_url)
        caption = soup.find('td', id='cellCaptionText').text.strip()
        authors = soup.find('td', id='cellAuthors').text.strip().replace(' |', ',')  # Not to mess with MD table
        last_action = soup.find('td', id='cellLastAction').text.strip()
        print("Caption: {}\nAuthors: {}\nLast Action: {}\n".format(caption, authors, last_action))
        return (caption, authors, last_action)
    except:
        return ("Unknown", "Unknown", "Unknown")


def lookup_bill_text(bill_number, url=BILL_TEXT_URL):
    populated_url = url.format(bill_number)
    soup = fetch_and_parse(populated_url)
    links = soup.find_all("a", href=True)
    htm_links = []
    for link in links:
        if link["href"].endswith(".htm"):
            htm_links.append(TLO_BASE_URL + link["href"])

    # FIXME: Assume the last one is the useful one
    # Can be an issue later as bill proceeds
    bill_text_url = htm_links[-1]

    return requests.get(bill_text_url).text

def understand_bill(bill_text):
    prompt = f"""
You are a legal expert specialized in analyzing the potential impacts of legislature bills, specifically those impacts to immigrants from certain nations or countries.

You will be given the following input:
<BillText>: Text of the bill in HTML format

Your task is to do the following 3 tasks:
1. Summarize the bill text in less than 80 words:
  - Be explicit if the Chinese immigrants are impacted.
  - No need to include the date when the bill become effective.
  - Discuss the potential effect of the bill to any Chinese in the US. Even if some bills are targeting Chinese goverment, discuss the potential impact to Chinese personals.

2. Translate the <Summary> into Chinese.

3. List the most possible 3 committees this bill will be sent to.

4. Categorize the bill into one of the following category:
  - Alien land laws: including but not limited to bills restricting immigrants' right to purchase real property, farm land, natural resources, etc.
  - Education: including but not limited to bills restricting immigrants' right to education (public schools and universities)
  - Contracting and Investment: including but not limited to bills restricting immigrants' right to receive contracts or investments
  - Immigration: including but not limited to bills punishing immigrants due to their entry or using health care services
  - Others: any bills that cannot be categorized above
  - Irrelevant: the bills does not mention specific countries or target immigrants of certain nations

Follow this output format:
<Summary>
[Your summary of the bill's imapct to immigrants]
</Summary>
<Translation>
[Your translation of the summary into Chinese]
</Translation>
<Committees>
1. [Most Possible Committee the bill will be assigned to]
2. [2nd Most Possible Committee the bill will be assigned to]
3. [3rd Most Possible Committee the bill will be assigned to]
</Committees>
<Category>
[Your classification of category]
</Category>

The bill text is as follows:
<BillText>
{bill_text}
<BillText>
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
            inferenceConfig={"maxTokens": DEFAULT_MAX_TOKENS, "temperature": DEFAULT_TEMPERATURE, "topP": DEFAULT_TOP_P},
        )

        # Extract and print the response text.
        response_text = response["output"]["message"]["content"][0]["text"]
        print(f"Response:\n{response_text}\n")
        return response_text

    except (ClientError, Exception) as e:
        print(f"ERROR: Can't invoke '{MODEL_ID}'. Reason: {e}")
        return UNDERSTANDING_ERROR

def understand_bills(bills, url):
    for bill in bills[:]:
        print(f"Processing bill {bill}...")

        should_understand = True
        if os.path.isfile(f"data/{bill}.json"):
            print(f"Bill {bill} already understood, loading...")
            with open(f"data/{bill}.json") as dataf:
                bill_data = json.load(dataf)
                bill_url = bill_data["url"]
                caption = bill_data["caption"]
                authors = bill_data["authors"]
                last_action = bill_data["last_action"]
                summary = bill_data["summary"]
                translation = bill_data["translation"]
                committees = bill_data["committees"]
                category = bill_data["category"]
            new_caption, new_authors, new_last_action = lookup_bill_info(bill)
            if new_caption == caption and new_authors == authors and new_last_action == last_action:
                print(f"Bill {bill} has not been updated, skipping...")
                should_understand = False
            else:
                print(f"ALERT! Bill {bill} has been updated, understanding again...")

        if should_understand:
            print(f"Understand bill {bill}...")
            bill_url = url.format(bill)
            caption, authors, last_action = lookup_bill_info(bill)
            bill_text = lookup_bill_text(bill)
            undersanding = understand_bill(bill_text)
            if undersanding != UNDERSTANDING_ERROR:
                undersanding_xml = f"<root>{undersanding}</root>"
                summary = extract_string_by_tag(undersanding_xml, "Summary").replace("\n", "<br>")
                translation = extract_string_by_tag(undersanding_xml, "Translation").replace("\n", "<br>")
                committees = extract_string_by_tag(undersanding_xml, "Committees").replace("\n", "<br>")
                category = extract_string_by_tag(undersanding_xml, "Category").replace("\n", "")
                bill_data = {
                    "number": bill,
                    "url": bill_url,
                    "caption": caption,
                    "authors": authors,
                    "last_action": last_action,
                    "summary": summary,
                    "translation": translation,
                    "committees": committees,
                    "category": category
                }
                with open(f"data/{bill}.json", "w") as dataf:
                    json.dump(bill_data, dataf)
            time.sleep(POLL_INTERVAL)

def track_priority_bills(url):
    for i in range(30):
        bill = f"SB{i+1}"
        if bill == "SB17":
            continue
        bill_url = url.format(bill)
        caption, authors, last_action = lookup_bill_info(bill)
        bill_data = {
            "number": bill,
            "url": bill_url,
            "caption": caption,
            "authors": authors,
            "last_action": last_action
        }
        with open(f"data/{bill}.json", "w") as dataf:
            json.dump(bill_data, dataf)

if __name__ == "__main__":
    print("Collecting bills to understand...")
    if not os.path.isfile("bills_to_understand.txt"):
        raise Error("bills_to_understand.txt not found")
    else:
        with open('bills_to_understand.txt') as f:
            bills = f.read().splitlines()
            bills_sorted = sorted(bills, key=lambda x: (x[:2], int(x[2:])))
            print(f"Sorted bills: {bills_sorted}")
    print("Understanding bills ...")
    understand_bills(bills_sorted, BILL_HISTORY_URL)
    track_priority_bills(BILL_HISTORY_URL)
