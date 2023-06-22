from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import os
from typing import List, Tuple, TypedDict
import pandas as pd
from pprint import pprint
from infinite_scroll import infinite_scroll


class ItemLink(TypedDict):
    link: str


amazon_domain = "https://www.amazon.co.jp"


def get_item_links(driver, url: str) -> Tuple[List[ItemLink], str]:
    driver.get(url=url)

    infinite_scroll(driver=driver)

    html = driver.page_source.encode("utf-8")
    soup = BeautifulSoup(html, "lxml")

    item_elements = soup.find_all(
        "div", class_="rush-component s-featured-result-item s-expand-height"
    )
    item_links: List[ItemLink] = []
    for item_element in item_elements:
        item_link = amazon_domain + item_element.find(
            "a", class_="a-link-normal s-no-outline"
        ).get("href")
        item_links.append({"link": item_link})

    next_page_link_element = soup.find(
        "a",
        class_="s-pagination-item s-pagination-next s-pagination-button s-pagination-separator",
    )
    next_page_link = amazon_domain + next_page_link_element.get("href")
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
    options.add_argument("--user-agent=hogehoge")

    driver = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()), options=options
    )

    url = "https://www.amazon.co.jp/s?i=beauty&rh=n%3A170121011&fs=true&qid=1687415177&ref=sr_pg_2"

    item_links: List[ItemLink] = []
    while len(item_links) < 500:
        result_item_links, result_next_page_link = get_item_links(
            driver=driver, url=url
        )
        url = result_next_page_link
        item_links.extend(result_item_links)

    df = pd.DataFrame(item_links)
    df.to_csv(f"{current_path}/csv/item_link/{category_name}.csv")


if __name__ == "__main__":
    main()
