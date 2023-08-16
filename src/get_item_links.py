from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import os
from typing import List, Tuple, TypedDict, Union
import pandas as pd
from pprint import pprint
import random
from infinite_scroll import infinite_scroll


class ItemLink(TypedDict):
    name: str
    link: str


amazon_domain = "https://www.amazon.co.jp"


def get_item_links(driver, url: str) -> Tuple[List[ItemLink], Union[str, None]]:
    driver.get(url=url)

    infinite_scroll(driver=driver)

    html = driver.page_source.encode("utf-8")
    soup = BeautifulSoup(html, "lxml")

    item_name_elements = soup.find_all(
        "h2",
        class_="a-size-mini a-spacing-none a-color-base s-line-clamp-4",
    )
    item_links: List[ItemLink] = []
    for item_name_element in item_name_elements:
        item_name = item_name_element.get_text(strip=True)
        item_link = amazon_domain + item_name_element.find("a").get("href")
        item_links.append({"name": item_name, "link": item_link})

    next_page_link_element = soup.find(
        "a",
        class_="s-pagination-item s-pagination-next s-pagination-button s-pagination-separator",
    )

    next_page_link = (
        amazon_domain + next_page_link_element.get("href")
        if next_page_link_element
        else None
    )
    # if next_page_link_element:
    #     next_page_link = amazon_domain + next_page_link_element.get("href")
    #     links = get_item_links(driver=driver, url=next_page_link)
    #     item_links.extend(links)

    return item_links, next_page_link


def main():
    current_path = os.path.dirname(os.path.abspath(__file__))
    category_name = "emulsion_cleam"

    options = webdriver.ChromeOptions()
    options.add_argument("--headless")

    user_agent = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.2 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36",
    ]
    UA = user_agent[random.randrange(0, len(user_agent), 1)]
    options.add_argument("--user-agent=" + UA)

    driver = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()), options=options
    )

    url = "https://www.amazon.co.jp/s?i=beauty&rh=n%3A170121011&fs=true&qid=1687415177&ref=sr_pg_2"

    item_links: List[ItemLink] = []
    while len(item_links) < 1000 and url:
        result_item_links, result_next_page_link = get_item_links(
            driver=driver, url=url
        )
        url = result_next_page_link
        item_links.extend(result_item_links)

    df = pd.DataFrame(item_links)
    df = df.drop_duplicates(subset="name")
    df = df.reset_index(drop=True)
    df.to_csv(f"{current_path}/csv/item_link/{category_name}.csv")


if __name__ == "__main__":
    main()
