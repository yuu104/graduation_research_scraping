from time import sleep


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
