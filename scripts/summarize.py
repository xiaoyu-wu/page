from botocore.exceptions import ClientError
from utils import extract_string_by_tag
from llm_utils import *
import datetime
import json
import os

def generate_summary(category, previous_summary, bill_summarys):

    prompt = f"""
You are a legislature expert specialized in summarizing legislature bills.

You will be given the following input:
<Category>: The focus of the bills and the specific area the bills is trying to regulate
<Bills>: The bills of the same <Category> and each <Bill> represented by <BillNumber> and <BillSummary> tags
<PreviousSummary>: Previous summary of the bills. Note the summary may be incomplete as some bills are not included or some bills have been updated. If there was no previous summary, this part will be empty.

Your task is to do the following 2 tasks:
1. Summarize the bills and their potential impact
  - Start with a brief introduction about common focus for normla bills in the domain of <Category>
  - For alian land laws, point out its discriminative nature
  - Reference bills by their numbers
  - Make sure every bill is mentioned
  - Be explicit if the Chinese immigrants are impacted.
  - Discuss the potential effect of the bill to any Chinese in the US. Even if some bills are targeting Chinese goverment, discuss the potential impact to Chinese personals.
  - If no major change is needed, try to follow the <PreviousSummary> and make minor updates, e.g. by including more bill numbers into original bullet points. However, do not assume readers have read the previous version.

2. Translate the <Summary> into Chinese

Follow this output format:
<Summary>
[Your summary of the bills and their imapct to immigrants]
</Summary>
<Translation>
[Your translation of the summary into Chinese]
</Translation>

The input is as follows:
<Category>
{category}
</Category>
<PreviousSummary>
{previous_summary}
</PreviousSummary>
<Bills>
{bill_summarys}
</Bills>
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
        previous_summary = ""
        if os.path.isfile(f"summary/{category}.json"):
            print(f"Category {category} already summarized. Will update sumamry based on it.")
            with open(f"summary/{category}.json") as previous_summary_f:
                previous_summary_json = json.load(previous_summary_f)
                previous_summary = previous_summary_json["english"]
        bills_text = "".join([
            f"<Bill>\n<BillNumber>{bn}</BillNumber>\n<BillSummary>{summary}</BillSummary>\n</Bill>\n" for (bn, summary) in categories[category]
        ])
        print(f"Category: {category}\nPrevious Summary: {previous_summary}\nBills: {bills_text}\n")
        summary = generate_summary(category, previous_summary, bills_text)
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
    with open("bills_scanned.txt") as f:
        bills = f.read().splitlines()
    with open("bills_patch.txt") as f:
        bills_patch = f.read().splitlines()
    for bill in bills_patch:
        if bill not in bills:
            bills.append(bill)
            print(f"Added: {bill}")
    with open("bills_irrelevant.txt") as f:
        bills_irrelevent = f.read().splitlines()
        for bill in bills_irrelevent:
            if bill in bills:
                bills.remove(bill)
                print(f"Removed: {bill}")
    bills_sorted = sorted(bills, key=lambda x: (x[:2], int(x[2:])))
    with open("bills_to_understand.txt", "w") as f:
        for bill in bills_sorted:
            f.write(bill + '\n')
    print(f"Sorted bills: {bills_sorted}")
    print("Summarzing bills by category ...")
    summarize_bills_by_category(bills_sorted)
