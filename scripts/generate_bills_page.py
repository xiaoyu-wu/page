import datetime
import json
import os

CATEGORIES = [
    "Alien land laws",
    "Education",
    "Contracting and Investment",
    "Immigration",
    "Others"
]

def build_section_for_category(category):
    with open(f"bills_section.template.md") as f:
        section_template = f.read()
    with open(f"summary/{category}.json") as f:
        summary = json.load(f)
    with open(f"summary/bills_table-{category}.md") as f:
        bills_table = f.read()
    section = section_template.format(
        category=category,
        summary=summary["english"],
        translation=summary["chinese"],
        table=bills_table
    )
    return section

def update_bills_page():
    with open("bills.md.template") as f:
        content = f.read()
    for category in CATEGORIES:
        print(f"Building section for category {category}...")
        content += build_section_for_category(category)
        if category == "Alien land laws":
            with open("talking_points_sb17.md") as f:
                tp = f.read()
            content += f'''
### Talking Points Against SB17
{tp}
'''
    content += build_section_for_priority_bills()
    with open("../bills.markdown", "w") as f:
        f.write(content)

def build_section_for_priority_bills():
    bills = [f"SB{i+1}" for i in range(30)]
    return "## Priority Bills Status\n" + build_bills_table(bills)

def build_bills_table(bills):
    content = ''
    content += f"Last Updated at {datetime.datetime.now().strftime('%H:%M:%S %Y-%m-%d')}\n\n"
    content += f"|Bill Number|Caption|Authors|Last Actiond|\n"
    content += f"|{"-|" * 4}\n"
    for bill in bills[:]:
        if os.path.isfile(f"data/{bill}.json"):
            with open(f"data/{bill}.json") as dataf:
                bill_data = json.load(dataf)
                bill_url = bill_data["url"]
                caption = bill_data["caption"]
                authors = bill_data["authors"]
                last_action = bill_data["last_action"]
        else:
            raise RuntimeError(f"Data for Bill {bill} not found")
        content += "|[{}]({})|{}|{}|{}|\n".format(bill, bill_url, caption, authors, last_action)
    return content


if __name__ == "__main__":
    print("Updating bills page ...")
    update_bills_page()
