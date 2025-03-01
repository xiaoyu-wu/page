import requests
from bs4 import BeautifulSoup

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

def extract_string_by_tag(xml_string, tag_name):
    soup = BeautifulSoup(xml_string, 'xml')
    tag = soup.find(tag_name)
    return tag.text if tag else ''
