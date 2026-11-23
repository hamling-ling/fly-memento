# 実機アプリ（Arduino UNO Q）

Linux 側がカメラと脳とバツ画面、マイコン側が車輪。学習の手順はリポジトリ直下の README にある。

## 動かし方

PC から `arduino@uno-q-1.local` へ SSH の鍵で入る。ボードに `arduino-app-cli` と Docker がある。リポジトリのどこからでも実行できる。

```bash
scripts/deploy_fly-memento.sh
```

- 別のホストへ置くとき: `scripts/deploy_fly-memento.sh arduino@<ホスト名>.local`
- スケッチを必ず作り直すとき: `--rebuild`
- 送るファイルとハッシュだけ見るとき: `--dry-run`（SSH しない）

ボード上の置き場所は `~/ArduinoApps/fly-memento`。`brain/` は `python/brain` に同梱する。アプリだけでは `brain` を import できないためである。Python だけの更新では `.cache` を残し、`app.yaml` か `sketch/` が `~/ArduinoApps/fly-memento/.sketch-hash` と違うとき、または `--rebuild` のときはキャッシュを消してコンパイルする。

手で起動・停止するときは SSH で入る。

```bash
ssh arduino@uno-q-1.local
arduino-app-cli app start ~/ArduinoApps/fly-memento/
arduino-app-cli app stop ~/ArduinoApps/fly-memento/
```

ログは PC で取る。画面に流れ、同じ内容が `logs/fly-memento-日時.log` に残る（`logs/` は git に入らない）。

```bash
scripts/logs_fly-memento.sh
```

止まっているときは 1 秒に 1 行、動いているあいだは 0.1 秒ごと。`red`、`blue`、`punish`、`avoid`、`mbon`、`ARM`、`LTM`、`pulse` が出る。ボード上で見る場合は `arduino-app-cli app logs ~/ArduinoApps/fly-memento/ --follow --tail 30`。

スマホは同じネットワークから `http://<UNO Q のアドレス>:8000/` を開く。ポートは `app.yaml` の 8000。画面の「バツ」が罰である。赤が見えているあいだに押す。青は罰なし。起動ログに `バツ画面` とこのポートが出る。

カメラは赤を CS+、青を CS− として数える。数え方は fly-car と同じで、門は `python/color_thresholds.json`（赤は色相 322° 以上、彩度 100、明度 120。青は 180–220°、彩度 160、明度 70）。眼の割合が `fraction_floor`（0.05）未満は脳に渡さない。色が無いときの車輪は 0 である。探索の前進が要るときは `config.py` の `EXPLORE_BIAS` を 0.35 にする。パネルが見えているのにパルスが 0 のままなら、`COLOR_GAIN` を上げる。色相 0° や 240° のパネルを落とすときは、JSON の `hue_low` か `hue_high` を広げる。

`No Colon In First Item Of Depfile` と出たら、スケッチのキャッシュが壊れている。`--rebuild` を付けて配置し直す。

チェックアウトのまま画面だけ見るときは `python3 robot/python/main.py --dry`。このときは `brain/` が `robot/` の隣にある。
