import boto3
import requests
from bs4 import BeautifulSoup
from botocore.exceptions import ClientError
from botocore.config import Config
import os
import time
import datetime
import json
from utils import fetch_and_parse

BILL_HISTORY_URL = "https://capitol.texas.gov/BillLookup/History.aspx?LegSess=89R&Bill={}"
BILL_TEXT_URL = "https://capitol.texas.gov/BillLookup/Text.aspx?LegSess=89R&Bill={}"
TLO_BASE_URL = "https://capitol.texas.gov"

POLL_INTERVAL = 10  # Time in seconds between each poll

retry_config = Config(
    retries={
        "max_attempts": 5,
        "mode": "adaptive",
    }
)

CLIENT = boto3.client("bedrock-runtime", region_name="us-west-2", config=retry_config)
MODEL_ID = "anthropic.claude-3-5-sonnet-20241022-v2:0"
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.3
DEFAULT_TOP_P = 0.9

UNDERSTANDING_ERROR = "Error: Unable to understand the bill."

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

def extract_string_by_tag(xml_string, tag_name):
    soup = BeautifulSoup(xml_string, 'xml')
    tag = soup.find(tag_name)
    return tag.text if tag else None

def update_bills_table(bills, url):
    with open("bills_table.md", "w") as f:
        f.write(f"Last Updated at {datetime.datetime.now().strftime('%H:%M:%S %Y-%m-%d')}\n\n")
        f.write("|Bill Number|Summary|Translation|Category|Committees|Caption|Authors|Last Actiond|\n")
        f.write("|-|-|-|-|-|-|-|-|\n")
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
            f.write("|[{}]({})|{}|{}|{}|{}|{}|{}|{}|\n".format(bill, bill_url, summary, translation, category, committees, caption, authors, last_action))

def generate_summary(bill_summarys):

    prompt = f"""
You are a legislature expert specialized in summarizing legislature bills.

You will be given the following input:
<Category>: The focus of the bills and the specific area the bills is trying to regulate
<Bills>: The bills of the same <Category> and each <Bill> represented by <BillNumber> and <BillSummary> tags

Your task is to do the following 2 tasks:
1. Summarize the bills and their potential impact
  - Start with a brief introduction about common focus for normla bills in the domain of <Category>
  - For alian land laws, point out its discriminative nature
  - Reference bills by their numbers
  - Be explicit if the Chinese immigrants are impacted.
  - Discuss the potential effect of the bill to any Chinese in the US. Even if some bills are targeting Chinese goverment, discuss the potential impact to Chinese personals.

2. Translate the <Summary> into Chinese

Follow this output format:
<Summary>
[Your summary of the bills and their imapct to immigrants]
</Summary>
<Translation>
[Your translation of the summary into Chinese]
</Translation>

The input is as follows:
{bill_summarys}
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

def summarize_bills_by_category(bills):
    categories = {}
    for bill in bills:
        with open(f"data/{bill}.json") as dataf:
            bill_data = json.load(dataf)
        category = bill_data["category"]
        if category not in categories:
            categories[category] = []
        categories[category].append((bill, bill_data['summary'].replace("<br>", "\n")))
    for category in categories:
        cat_bills = [bill for (bill, _) in categories[category]]
        build_bills_table(cat_bills, f"summary/bills_table-{category}.md", includeCategory=False)

        print(f"Summarizing category: {category}")
        if os.path.isfile(f"summary/{category}.json"):
            print(f"Category {category} already summarized. Delete file to regenerate summary.")
            continue
        aggregated_text = f"<Category>{category}</Category>\n"
        bills_text = "".join([
            f"<Bill>\n<BillNumber>{bn}</BillNumber>\n<BillSummary>{summary}</BillSummary>\n</Bill>\n" for (bn, summary) in categories[category]
        ])
        aggregated_text += f"<Bills>\n{bills_text}</Bills>\n"
        print("Aggregated input:\n" + aggregated_text)
        summary = generate_summary(aggregated_text)
        print("Summary:\n" + summary)
        summary_xml = f"<root>{summary}</root>"
        summary_json = {
            "english": extract_string_by_tag(summary_xml, "Summary"),
            "chinese": extract_string_by_tag(summary_xml, "Translation")
        }
        with open(f"summary/{category}.json", "w") as f:
            json.dump(summary_json, f)


def build_bills_table(bills, file_name, includeCategory=False):
    with open(file_name, "w") as f:
        f.write(f"Last Updated at {datetime.datetime.now().strftime('%H:%M:%S %Y-%m-%d')}\n\n")
        f.write(f"|Bill Number|Summary|Translationd{"|Category" if includeCategory else ""}|Committees|Caption|Authors|Last Actiond|\n")
        f.write(f"|{"-|" * 7}{"-|" if includeCategory else ""}\n")
        for bill in bills[:]:
            print(f"Processing bill {bill}...")

            if os.path.isfile(f"data/{bill}.json"):
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
            else:
                raise RuntimeError(f"Data for Bill {bill} not found")
            if includeCategory:
                f.write("|[{}]({})|{}|{}|{}|{}|{}|{}|{}|\n".format(bill, bill_url, summary, translation, category, committees, caption, authors, last_action))
            else:
                f.write("|[{}]({})|{}|{}|{}|{}|{}|{}|\n".format(bill, bill_url, summary, translation, committees, caption, authors, last_action))


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
    update_bills_table(bills_sorted, BILL_HISTORY_URL)
    summarize_bills_by_category(bills_sorted)
