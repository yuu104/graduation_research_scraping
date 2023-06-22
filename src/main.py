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
import re
import demoji
import time

amazon_domain = "https://www.amazon.co.jp"


class ReviewData(TypedDict):
    rating: int
    title: str
    content: str
    useful_count: int


def clean_text(text: str) -> str:
    # 句読点を改行コードに変換
    text = re.sub(r"[。、！？．…,.!?]+", lambda match: "\n" * len(match.group()), text)

    # 小文字変換
    text = text.lower()

    # URL除去
    text = re.sub(r"http?://[\w/:%#\$&\?\(\)~\.=\+\-]+", "", text)
    text = re.sub(r"https?://[\w/:%#\$&\?\(\)~\.=\+\-]+", "", text)

    # 改行コードを揃える
    text = text.replace("\r", "\n")

    # 絵文字除去
    text = demoji.replace(string=text, repl="")

    # 半角記号除去
    text = re.sub(
        r"[!”#$%&\’\\\\()*+,-./:;?@[\\]^_`{|}~「」〔〕“”〈〉『』【】＆＊・（）＄＃＠。,？！｀＋￥％※・]",
        "",
        text,
    )

    # 全角記号除去
    text = re.sub(
        "[\uFF01-\uFF0F\uFF1A-\uFF20\uFF3B-\uFF40\uFF5B-\uFF65\u3000-\u303F]", "", text
    )

    return text


def remove_stopword(text: str) -> str:
    strings = ["商品の説明", "この商品について", "ブランド紹介", "商品紹介", "原材料・成分"]
    # 正規表現パターンを生成
    pattern = r"|".join(map(re.escape, strings))

    # パターンに一致する文字列を空文字に置換して取り除く
    removed_text = re.sub(pattern, "", text)

    return removed_text


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
    ids = [
        "featurebullets_feature_div",
        "productDescription",
        "aplus",
        "aplus_feature_div",
        "visual-rich-product-description",
    ]

    text = ""
    for element_id in ids:
        description_element = soup.find("div", id=element_id)
        if not description_element:
            continue

        style_tags = description_element.find("style")
        script_tags = description_element.find("script")
        description_element.find("style").extract() if style_tags else None
        description_element.find("script").extract() if script_tags else None
        text += remove_stopword(description_element.get_text(strip=True))

    text = clean_text(text=text)
    return text if not text == "" else None


def get_reviews(driver, url: str) -> List[ReviewData]:
    driver.get(url)

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
        review_title = (
            review_element.find("a", class_="review-title").get_text(strip=True)
            if review_element.find("a", class_="review-title")
            else None
        )
        review_content = (
            clean_text(
                review_element.find(
                    "span", class_="a-size-base review-text review-text-content"
                ).get_text(strip=True)
            )
            if review_element.find(
                "span", class_="a-size-base review-text review-text-content"
            )
            else None
        )
        if not review_title or not review_content:
            continue
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

    infinite_scroll(driver=driver)

    html = driver.page_source.encode("utf-8")
    soup = BeautifulSoup(html, "lxml")

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
    options.add_argument("--user-agent=hogehoge")

    driver = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()), options=options
    )

    url = "https://www.amazon.co.jp/%E3%82%A4%E3%83%8B%E3%82%B9%E3%83%95%E3%83%AA%E3%83%BC-innisfree-%E3%83%8E%E3%83%BC%E3%82%BB%E3%83%90%E3%83%A0-%E3%83%9F%E3%83%8D%E3%83%A9%E3%83%AB%E3%83%91%E3%82%A6%E3%83%80%E3%83%BC-N/dp/B097GR6ZQ7/ref=cm_cr_arp_d_product_top?ie=UTF8"

    start_time = time.time()

    save_item_data(
        driver=driver,
        url=url,
    )

    end_time = time.time()
    print(f"経過時間：{end_time - start_time}")


if __name__ == "__main__":
    main()
