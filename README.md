# fly-memento

罰を覚える二輪の虫。ショウジョウバエのキノコ体を縮約した脳で、Arduino UNO Q の上を走る。前作 [fly-car](https://github.com/hamling-ling/fly-car) は接近と逃避だった。こちらはその後継で、緑（CS+）で受けた罰を、圧縮した「翌日」にも避ける。

**English.** A two-wheel robot whose brain is a reduced fruit-fly mushroom body. The Linux side of an Arduino UNO Q reads colour and steps the neurons; the microcontroller drives the motors on D3 and D5. A phone on the same network opens `http://<UNO Q>:8000/` and presses バツ. Deploy with `scripts/deploy_fly-memento.sh` and follow the run with `scripts/logs_fly-memento.sh`. The arena simulation reproduces the research result: spaced training still avoids at 72 h (PI about 70) while massed training has faded (about 45).

## 何をつないでいるか

一本の鎖である。

1. **配線。** オス全脳のコネクトーム（FlyEM MaleCNS v1.0）で、キノコ体の区画と伝達物質を数える。ロボが使うのは、その読み出しから正規化した3区画の重み（おおよそ 0.21 / 0.46 / 0.33）だけ。
2. **力学。** ドーパミン細胞 PPL101（MP1）と PPL103（MV1）の2細胞振動子。差で結ぶ ε は、ギャップ結合の**作業仮説**である。
3. **記憶。** 不安定な痕跡 S、中期の ARM、長期の LTM。分散（間隔が長い）だと LTM が乗り、集中（間隔が短い）だと ARM だけで、疲労で振動が弱る。
4. **行動。** 生得的には、明るい方の反対の車輪が速くなり、光へ曲がる（fly-car の DNa02 と同じ向き）。学習した回避は同側で、罰の色からそれる。
5. **ロボ。** カメラの緑と黄が投射ニューロンになり、脳が 50 Hz（20 ms）で進み、車輪指令は RPC でマイコンへ渡る。

時間は圧縮できる。標準は **1 ロボット秒 = 1 生物分** なので、生物の 1 時間が 1 分、24 時間が 24 分、72 時間が 72 分。`compression=5` にすると 1 秒が 5 生物分になり、24 時間は 4.8 分で済む。振動子そのものはロボットの実時間で回り、周期はおおよそ 10 秒である。

## 置き場所

```
brain/     シミュレーションと実機が共有する脳。時間圧縮は引数
sim/       1 m のアリーナ。分散・集中・εなし・振動子オフ
robot/     UNO Q の App Lab アプリ（Python、バツ画面、D3/D5 のスケッチ）
scripts/   UNO Q へ robot/ と brain/ を置き、ログを PC に残す
docs/      数式（MODEL.md）、設計メモ、研究ログ、ポスター、アーカイブした表
tests/     脳の決定性、状態の大きさ、バツ画面
```

## シミュレーション

Linux と Python 3.11 以降。実機は要らない。

```bash
python3 -m pip install -r requirements.txt
python3 -m pytest
python3 -m sim
```

`python3 -m sim` が表と `sim/out/retention.png` を書く。標準は振動子セット 4 個 × 試行 12 で、1 分前後で終わる。研究ログの表（10 セット × 40 試行、PI は 72 時間で分散 約 70、集中 約 45）を、同じ式の短い再実行で並べる。点線がアーカイブ、実線が今回である。`--seeds` と `--trials` で伸ばせる。`--quick` は野生型の 72 時間だけ。

アーカイブそのものは `docs/results/summary_by_condition.csv` にある。

## 実機で教える（約 30 分）

配置と起動はスクリプトで行う。PC からボードへ SSH の鍵で入れること（パスワードを訊かない `BatchMode`）。ボードは Debian の Arduino UNO Q で、`arduino-app-cli` と Docker が入っている。リポジトリのどこからでも実行でき、送り先は `arduino@uno-q-1.local`、置き場所は `~/ArduinoApps/fly-memento` である。

```bash
scripts/deploy_fly-memento.sh
```

- 別のホストへ置くとき: `scripts/deploy_fly-memento.sh arduino@<ホスト名>.local`
- スケッチを必ず作り直すとき: `--rebuild`（`app.yaml` と `sketch/` が前回と違うときもキャッシュを消す）
- SSH せずに、送る中身とスケッチのハッシュだけ見るとき: `--dry-run`

スクリプトはアプリを止めて、`robot/`（`app.yaml`、`python/`、`sketch/`、`assets/`）をコピーし、共有の `brain/` を `python/brain` に置いてから起動する。App Lab はアプリの `python/` を import パスに入れるので、ボード上の `import brain` はそこを読む。Python だけの更新では `.cache` を残し、仮想環境とコンパイル済みのスケッチを次の起動が使う。

手で起動・停止するときは SSH で入る。起動コマンドはシェルに戻る。

```bash
ssh arduino@uno-q-1.local
arduino-app-cli app start ~/ArduinoApps/fly-memento/
arduino-app-cli app stop ~/ArduinoApps/fly-memento/
```

`No Colon In First Item Of Depfile` と出たら、スケッチのキャッシュが壊れている。`scripts/deploy_fly-memento.sh --rebuild` で消してから起動し直す。

ログは PC で取る。画面に流れ、同じ内容が `logs/fly-memento-日時.log` に残る（`logs/` は git に入らない）。Ctrl-C で切る。ファイルは残る。

```bash
scripts/logs_fly-memento.sh
scripts/logs_fly-memento.sh arduino@<ホスト名>.local
```

止まっているときは 1 秒に 1 行。色が見えている、回避している、車輪が回っているあいだは 0.1 秒ごと。罰・パルス・周・モードが変わったときも 1 行。各行に `punish`、`avoid`、`mbon`（3 区画）、`ARM`、`LTM`、`pulse` が出る。ボード上で見る場合は `arduino-app-cli app logs ~/ArduinoApps/fly-memento/ --follow --tail 30`。

スマホは同じネットワークで `http://<UNO Q のアドレス>:8000/` を開く。ページは Python 標準ライブラリが出している。起動ログに `バツ画面  http://<この機械のアドレス>:8000/` と出る。App Lab の web_ui ブリックは使っていない。脳と同じプロセスにある方が、ボタン1個には短い。

リポジトリごとボードに置いて App Lab で `robot/` を開いても動く。そのときは `brain/` を `robot/` の隣に残す。スクリプトで置く場合は、隣ではなく `python/brain` に入る。カメラは fly-car と同じく Linux 側。マイコンのスケッチは右車輪 D3、左車輪 D5 だけで、顔の LED はまだ無い。

ボードが無くても、車輪を送らずに画面だけ確認できる。

```bash
python3 robot/python/main.py --dry
```

圧縮 1（標準）での分散学習は、おおよそ次の通り。生物の 24 時間がロボットの 24 分になる。

1. 緑のパネルを CS+、黄を CS− として、スタートから 50 cm ほど前に置く。色の範囲は `robot/python/color_thresholds.json`。実機の照明では、fly-car と同じように取り直す必要がある。初期値は仮である。
2. 画面の「周を始める」を押す。訓練のあいだは、試行中の忘却を止める（シミュレーションの `in_train` と同じ）。
3. 緑へ走らせ、緑が見えているあいだに大きな「バツ」を押す。押した瞬間に活動していたケニヨン細胞だけが覚える。暗がりで押しても、ほとんど残らない。1 秒に 1 回まで。20 秒ほど。
4. 黄は罰なしで 20 秒。
5. 「周を終えて休む」を押し、15 秒休む。これが生物の 15 分で、長期記憶の間隔になる。
6. 2 から 5 を、合わせて 5 周。最初の休息では窓が開かない。2 周目の終わりに開き、その後の休息で LTM が書かれる。画面に「長期記憶の窓」と出る。
7. 24 分置く。生物の 24 時間。このあいだは休息のまま（忘却と固定化が進む）。
8. 緑と黄を左右に置き、緑を避けるかを見る。ε を切る、または振動子を切ると、長期側が弱る。画面のチェックがそのまま脳へ入る。

集中は、休息を 15 秒ではなく 2 秒にする。ARM は乗るが LTM は乗らず、72 分後（生物の 72 時間）には分散より薄い。

5 倍圧縮（`robot/python/config.py` の `COMPRESSION = 5`）なら、同じ 24 時間は 4.8 分、休息 15 生物分は 3 秒である。デモを短くするときのつまみで、式の上のプロトコルは変わらない。ただし試行の 20 秒も生物時間では 5 倍になるので、アーカイブの表とは同じ時計ではない。

車輪の m/s からパルスへの倍率は fly-car のままである。床で計り直していない。死角（前進 13 未満）は切ってある。暗いときのゆっくりした前進は、シミュレーションのバイアス（0.35）が残ったもので、意図した巡航ではない。

バンパは付けていない。罰は画面のバツだけである。D2 は空いている。

## 正直な注記

- **MP1–MV1 のギャップ結合 ε は作業仮説である。** 同時記録も、色素のカップリングも、イネキシンの操作も無い。共有入力だけではモデルが同期せず、同側の膜の近接は選択的で、ごく小さいコンダクタンスで足りる、というところまで。切ると同期が消え、一致検出（COI）では LTM が落ちる。平均（ADD）では落ちない。行動への効果は、下流が「同時」を読むか「平均」を読むかに掛かっている。
- **記憶の時定数はすべて仮定**である。定性的な向きは Plaçais 2012 と Berry 2012 に合わせた。`kL` は、圧縮した分散学習で LTM が見えるように、先行の行動モデルの 4 倍にしてある。集中の疲労（振動を −0.5 へ押す）は、データから導いたものではなく、外から置いている。
- 同梱した振動子の 4 セットは、周期・同期・ε=0 での一致の落ち方が設計メモのチェックに合うように選んだ代表である。研究ログの 111 セットからの抽選そのものではない。
- テストは脳のコピーで行い、試行の時間も消去も進まない。実機では 1 回の選択が数十秒かかり、そのあいだにも記憶は動く。
- センサは理想化している。カメラの緑と黄は、アリーナのランプの代理であり、同じ強度にはなっていない。`COLOR_GAIN` は仮のつまみである。
- 数値はモデルの中の話で、ハエで測った記憶量ではない。

式をコードに合わせて書いたものは [docs/MODEL.md](docs/MODEL.md)。設計の対応表、計算量（1 ステップ約 9600 flop、状態約 4.5 kB、50 Hz で M33 の 1% 未満）、ハードウェアの割り当ては [docs/DESIGN.md](docs/DESIGN.md)。研究ログは [docs/SUMMARY.md](docs/SUMMARY.md)。ポスターは [docs/poster/poncho_e.html](docs/poster/poncho_e.html)。

## ライセンス

MIT。Copyright (c) 2026 Nobuhiro Kuroiwa。
