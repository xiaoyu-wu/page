import json

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
    with open("../bills.markdown", "w") as f:
        f.write(content)



if __name__ == "__main__":
    print("Updating bills page ...")
    update_bills_page()
