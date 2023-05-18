from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from time import sleep
import os
from typing import List, Union, TypedDict
import pandas as pd
import ulid
from pprint import pprint

amazon_domain = "https://www.amazon.co.jp"


class ReviewData(TypedDict):
    rating: int
    title: str
    content: str
    useful_count: int


def infinite_scroll(driver) -> None:
    # 現在のウィンドウの高さを取得
    win_height = driver.execute_script("return window.innerHeight")

    # スクロール開始位置の初期化
    lastTop = 1

    # 無限スクロールページの最下部までループ
    while True:
        # スクロール前のページの高さを取得
        last_height = driver.execute_script("return document.body.scrollHeight")

        # スクロールの開始位置を設定
        top = lastTop

        # 最下部まで徐々にスクロールする
        while top < last_height:
            top += int(win_height * 0.8)
            driver.execute_script("window.scrollTo(0, %d)" % top)
            sleep(0.5)

        # スクロール後のページの高さを取得
        sleep(1)
        newLastHeight = driver.execute_script("return document.body.scrollHeight")

        # スクロール前後で高さに変化がなくなったら終了
        if last_height == newLastHeight:
            break

        # ループが終了しなければ現在の高さを再設定して次のループ
        lastTop = last_height


def get_item_detail_links(driver, url: str) -> List[str]:
    driver.get(url)

    # 無限スクロール
    infinite_scroll(driver=driver)

    html = driver.page_source.encode("utf-8")
    soup = BeautifulSoup(html, "html.parser")

    item_elements = soup.find_all("div", class_="p13n-sc-uncoverable-faceout")
    item_links = []
    for item in item_elements:
        a_tag = item.find("a")
        link = amazon_domain + a_tag.get("href")
        item_links.append(link)

    next_page_element = soup.find("li", class_="a-last")
    next_page_a_tag = next_page_element.find("a")
    if next_page_a_tag:
        next_page_link = amazon_domain + next_page_a_tag.get("href")
        links = get_item_detail_links(driver=driver, url=next_page_link)
        item_links.extend(links)

    return item_links


def get_description(soup: BeautifulSoup) -> Union[str, None]:
    description_element = soup.find("div", id="aplus")
    if not description_element:
        return None
    style_tags = description_element.find("style")
    description_element.find("style").extract() if style_tags else None
    description_element.find("script").extract() if style_tags else None
    text = description_element.get_text(strip=True).replace("商品の説明", "")
    return text


def get_reviews(driver, url: str) -> List[ReviewData]:
    driver.get(url)

    # 無限スクロール
    infinite_scroll(driver=driver)

    html = driver.page_source.encode("utf-8")
    soup = BeautifulSoup(html, "html.parser")

    review_datas: List[ReviewData] = []

    review_elements = soup.find_all("div", class_="a-section celwidget")
    for review_element in review_elements:
        rating_element = review_element.find("i", class_="a-icon-star")
        rating = int(
            [
                element.replace("a-star-", "")
                for element in rating_element.get("class")
                if "a-star-" in element
            ][0]
        )
        review_title = review_element.find("a", class_="review-title").get_text(
            strip=True
        )
        review_content = review_element.find(
            "span", class_="a-size-base review-text review-text-content"
        ).get_text(strip=True)
        useful_count_element = review_element.find(
            "span", class_="a-size-base a-color-tertiary cr-vote-text"
        )
        useful_count = (
            int(useful_count_element.get_text().replace("人のお客様がこれが役に立ったと考えています", ""))
            if useful_count_element
            else 0
        )

        review_data = {
            "rating": rating,
            "title": review_title,
            "content": review_content,
            "useful_count": useful_count,
        }
        review_datas.append(review_data)

    next_page_link_element = soup.find("li", class_="a-last").find("a")
    if next_page_link_element:
        next_page_link = amazon_domain + next_page_link_element.get("href")
        data = get_reviews(driver=driver, url=next_page_link)
        review_datas.extend(data)

    return review_datas


def save_item_data(driver, url: str) -> None:
    driver.get(url)

    # 無限スクロール
    infinite_scroll(driver=driver)

    html = driver.page_source.encode("utf-8")
    soup = BeautifulSoup(html, "html.parser")

    item_description = get_description(soup=soup)
    if not item_description:
        return

    review_page_link = amazon_domain + soup.find(
        "div", id="reviews-medley-footer"
    ).find("a").get("href")
    review_datas = get_reviews(driver=driver, url=review_page_link)

    item_description_df = pd.DataFrame(
        data=[[url, item_description]], columns=["item_link", "description"]
    )
    review_data_df = pd.DataFrame(
        data=review_datas, columns=["rating", "title", "content", "useful_count"]
    )

    current_path = os.path.dirname(os.path.abspath(__file__))
    item_id = ulid.new()
    os.makedirs(f"{current_path}/csv/{item_id.str}")
    item_description_df.to_csv(
        f"{current_path}/csv/{item_id.str}/{item_id.str}_description.csv"
    )
    review_data_df.to_csv(f"{current_path}/csv/{item_id.str}/{item_id.str}_review.csv")


def main():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")

    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()))

    # url = "https://www.amazon.co.jp/%E4%BC%8A%E8%97%A4%E4%B9%85%E5%8F%B3%E8%A1%9B%E9%96%80-%E5%AE%87%E6%B2%BB%E6%8A%B9%E8%8C%B6-%E8%A9%B0%E3%82%81%E5%90%88%E3%82%8F%E3%81%9B-%E5%90%89%E7%A5%A5%E5%85%AB%E8%A7%92-%E3%82%AB%E3%82%B9%E3%83%86%E3%83%A9%E3%83%BB%E7%BE%8A%E7%BE%B9%E5%85%A5%E3%82%8A/dp/B00JGKNS86/ref=zg_bs_71314051_sccl_1/356-4290058-4769442?th=1"

    # save_item_data(driver=driver, url=url)

    url = "https://www.amazon.co.jp/gp/bestsellers/food-beverage/71314051/ref=zg_bs_pg_1?ie=UTF8&pg=1"

    item_links = get_item_detail_links(driver=driver, url=url)

    for item_link in item_links:
        save_item_data(driver=driver, url=item_link)


if __name__ == "__main__":
    main()