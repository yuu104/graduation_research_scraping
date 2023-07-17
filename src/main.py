from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import os
from typing import List, Union, TypedDict
import pandas as pd
import ulid
from pprint import pprint
import re
import demoji
from concurrent.futures import ThreadPoolExecutor
import time
import random
from infinite_scroll import infinite_scroll

amazon_domain = "https://www.amazon.co.jp"
current_path = os.path.dirname(os.path.abspath(__file__))


class ReviewData(TypedDict):
    rating: int
    title: str
    content: str
    useful_count: int


def clean_text(text: str) -> str:
    # 句点を改行コードに変換
    text = re.sub(r"[。！？．….!?]+", lambda match: "\n" * len(match.group()), text)

    # 小文字変換
    text = text.lower()

    # URL除去
    text = re.sub(r"http?://[\w/:%#\$&\?\(\)~\.=\+\-]+", "", text)
    text = re.sub(r"https?://[\w/:%#\$&\?\(\)~\.=\+\-]+", "", text)

    # 改行コードを揃える
    text = text.replace("\r", "\n")

    # 絵文字除去
    text = demoji.replace(string=text, repl="")

    # 【】を除去
    text = text.replace("【", "").replace("】", "\n")

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


def get_item_detail_links(driver, url: str) -> List[str]:
    driver.get(url)

    # 無限スクロール
    infinite_scroll(driver=driver)

    html = driver.page_source.encode("utf-8")
    soup = BeautifulSoup(html, "lxml")

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

    sentence_list: List[str] = []
    for element_id in ids:
        description_element = soup.find("div", id=element_id)
        if not description_element:
            continue
        style_tags = description_element.find("style")
        script_tags = description_element.find("script")
        description_element.find("style").extract() if style_tags else None
        description_element.find("script").extract() if script_tags else None
        text = list(description_element.stripped_strings)
        text = list(map(remove_stopword, text))
        text = list(map(clean_text, text))
        text = list(filter(lambda sentence: len(sentence) != 0, text))
        sentence_list.extend(text)
    sentence_list = list(map(lambda sentence: sentence.rstrip("\n"), sentence_list))

    return "\n".join(sentence_list) if len(sentence_list) else None


def get_reviews(driver, url: str) -> List[ReviewData]:
    driver.get(url)

    # infinite_scroll(driver=driver)
    # WebDriverWait(driver=driver, timeout=30).until(
    #     EC.presence_of_element_located((By.CLASS_NAME, "a-last"))
    # )

    html = driver.page_source.encode("utf-8")
    soup = BeautifulSoup(html, "lxml")

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
        review_title_element = review_element.find("a", class_="review-title")
        if review_title_element:
            review_title_element.find("span", class_="a-icon-alt")
            review_element.find("span", class_="a-icon-alt").extract()
            review_title = review_element.find("a", class_="review-title").get_text(
                strip=True
            )
        else:
            review_title = None
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
            int(
                useful_count_element.get_text()
                .replace("人のお客様がこれが役に立ったと考えています", "")
                .replace(",", "")
            )
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

    next_page_link_element = soup.find("li", class_="a-last")
    if next_page_link_element and next_page_link_element.find("a"):
        next_page_link = amazon_domain + next_page_link_element.find("a").get("href")
        data = get_reviews(driver=driver, url=next_page_link)
        review_datas.extend(data)

    return review_datas


def save_item_data(driver, url: str) -> None:
    print(url)
    driver.get(url.replace(" ", ""))

    infinite_scroll(driver=driver)

    html = driver.page_source.encode("utf-8")
    soup = BeautifulSoup(html, "lxml")

    item_description = get_description(soup=soup)
    if not item_description:
        return

    review_page_link_element = soup.find("div", id="reviews-medley-footer")
    if not review_page_link_element:
        return
    review_page_link_a_tag = review_page_link_element.find("a")
    if not review_page_link_a_tag:
        return
    review_page_link = amazon_domain + review_page_link_a_tag.get("href")
    review_datas = get_reviews(driver=driver, url=review_page_link)

    item_description_df = pd.DataFrame(
        data=[[url, item_description]], columns=["item_link", "description"]
    )
    review_data_df = pd.DataFrame(
        data=review_datas, columns=["rating", "title", "content", "useful_count"]
    )

    item_id = ulid.new()
    os.makedirs(f"{current_path}/csv/{item_id.str}")
    item_description_df.to_csv(
        f"{current_path}/csv/{item_id.str}/{item_id.str}_description.csv"
    )
    review_data_df.to_csv(f"{current_path}/csv/{item_id.str}/{item_id.str}_review.csv")


def main():
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

    category_name = "emulsion_cleam"
    item_link_df = pd.read_csv(
        f"{current_path}/csv/item_link/{category_name}.csv", sep=",", index_col=0
    )
    item_links = item_link_df["link"].values[:101]

    start_time = time.time()
    with ThreadPoolExecutor() as executor:
        executor.map(save_item_data, item_links)
        for link in item_links:
            save_item_data(
                driver=driver,
                url=link,
            )
    end_time = time.time()
    print(f"経過時間：{end_time - start_time}")


if __name__ == "__main__":
    main()
