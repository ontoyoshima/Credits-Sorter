from flask import Flask, render_template, request
import pandas as pd
from io import TextIOWrapper

import json
from pathlib import Path
from functools import lru_cache
import logging


BASE = Path(__file__).parent / "data"
logging.basicConfig(
    level = logging.INFO,
    format = "%(asctime)s %(levelname)s %(name)s %(message)s"
)
logger = logging.getLogger(__name__)

def safe_path(year: str, code: str) -> Path:
    p = (BASE/ year / f"{code}.json").resolve()
    base_resolved = BASE.resolve() 
    # if not str(p).startswith(str(base_resolved) + ("" if str(base_resolved).endswith("/") else "/")):
    if not p.is_relative_to(base_resolved):
        raise ValueError("invalid path")
    return p

@lru_cache(maxsize=4096)
def load_syllabus(year: str, code: str) -> dict:
    p = safe_path(year, code)
    with p.open(encoding="utf-8") as f:
        return json.load(f)
    
# load_syllabus.cache_clear()

# 時間割コードによる分類ルール
def classify(code,faculty,grade):
    # 学部
    # 総合理工学部
    if faculty == "engineering":
        if grade <= 2024:
            if code.startswith("TA"):
                return "基盤科目"
            elif code.startswith("TB"):
                return "専門必修/専門選択/専門自由科目"
            elif code.startswith("TW"):
                return "自然科学系学部共通科目"
        if grade >= 2025:
            if code.startswith("TC"):
                return "理工共通基礎科目"
            elif code.startswith("TE"):
                return "理工社会実装教育科目"
            elif code.startswith(("TF","TG","TH","TJ")):
                return "専門人材教育科目"
    # 材料エネルギー学部
    if faculty == "material":
        if code.startswith("VA"):
            return "基盤科目"
        elif code.startswith("VB"):
            return "専門必修/専門選択科目"
    # # 生物資源科学部
    # elif code.startswith("WA"):
    #     return "基盤科目"
    # elif code.startswith("WT"):
    #     return "自然科学系学部共通科目"
    # # 法文学部
    # elif code.startswith("L"):
    #     return "専門科目"
    # # 人間科学部
    # elif code.startswith("R"):
    #     return "専門科目(人間)"
    # # 教育学部
    # elif code.startswith("M51") or code.startswith("M52"):
    #     return "専門共通科目(教育)"
    # elif code.startswith("NN"):
    #     return "教育体験活動"
    # elif code.startswith("M"):
    #     return "専門科目(教育)"
    # elif code.startswith("MC") or code.startswith("NS") or code.startswith("ND") or code.startswith("HS") or code.startswith("ME"):
    #     return "大学院"
    # 共通
    if code.startswith(("A1","A2","A3","A5","A6","UAA")): #UAA1-UAA7    1A:A1A1  1B:A1A2 2A:A2A1  2B:A2A2   A1A1081 A1A1641 A1A1161 A1A1201 A1A1231 A1A1681 A1A1331 A1A1741 A1A1751 A1A1611 1B:
        return "英語"
    # "UAB","UAC","UAD","UAE"      3年以上：# ドイツ語：A0B1 A0B2 フランス語：A0C2 A0C1 韓国：A0E1 A0E2 中国語：A0D2 A0D1
    elif code.startswith(("A0","UAB","UAC","UAD","UAE")):
        return "第二外国語"
        # 2024年度以降
    elif grade >= 2024 and code.startswith("UJC"):
        return "SDGs入門"
    # 健スポではないQBG6,7がいる問題なんならBも...
    elif code.startswith(("B","QBE","QBG")): # code.startswith(("B0A6","B0A7","QBG6","QBG7")): # sport実習
        if not (grade >= 2024 and faculty == "material"): 
            return "健康・スポーツ/文化・芸術等"
        elif code.startswith("QBE"):
            return "人文社会科学分野"
        elif code.startswith("QBG"):
            return "学際分野"
    elif code.startswith(("C","SC")):
        return "情報科学"
    elif code.startswith(("D","SD")):
        return "数理・データサイエンス"
    elif code.startswith(("E0","SE","SJE","UE","UJE","PE","QE")):
        return "人文社会科学分野"
    elif code.startswith(("F0","SF","SJF","UF","UJF","PF","PJF","QF")):
        return "自然科学分野"
    elif code.startswith(("G0","SG","SH","UG","UH","UJG","PG","PH","PJG","QG","QH","QJ")):
        return "学際分野"
    # 2023年度以前のみ
    elif grade <= 2023 and code.startswith("H0A"):
        return "社会人力養成科目"
    elif code.startswith("Z"):
        return "全学開放科目"
    elif code.startswith("X"):
        return "教職・学芸員"
    return "分類漏れ"

def get_credit(year: str, code: str):
    try:
        data = load_syllabus(year,code)
        if data["unit"] != None and data["unit"] != "":
                return float(data["unit"]),1
        # 数値が見つからなかった場合
        print(f"[警告] {year},{code} → 単位数を取得できませんでした。")
        return None,204
    
    except FileNotFoundError:
        print(f"[警告] 404")
        return None, 404
    except ValueError:
        print(f"[警告] 400")
        return None, 400
    except Exception as e:
        print(f"[警告] 500")
        logger.exception(e)
        return None, 500

app = Flask(__name__) # flask使うときの最初の決まり文句

@app.route("/",methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/result", methods=["POST"])
def result():
    num = 0
    # 結果を記録する変数
    result = {}
    # 単位数を取得できなかった講義名を記録する配列
    no_credit = []
    show_message = False
    if request.method == "POST":
        file = request.files.get("file")
        if file:

            faculty = request.form.get("faculty")
            grade = int(request.form.get("grade"))
            # pandasで5行目をカラム名として読み込む（index=4）
            df = pd.read_csv(TextIOWrapper(file, encoding="cp932"), skiprows=4) # TextIOWrapper アップロードされたバイナリファイルをテキストとして読み込むためのラッパー

            # 必要な列だけ抽出
            df = df[["開講年度","時間割コード", "開講科目", "合否"]]

            # 合格した講義だけ抽出
            df_passed = df[df["合否"] == "合"]

            # 区分ごとにリストに分け記録する変数
            categories = {"英語":[[0,0]],
                          "第二外国語":[[0,0]],
                          "健康・スポーツ/文化・芸術等":[[0,0]],
                          "情報科学":[[0,0]],
                          "数理・データサイエンス":[[0,0]],
                          "人文社会科学分野":[[0,0]],
                          "自然科学分野":[[0,0]],
                          "学際分野":[[0,0]]
                        }
            # 2023年度以降入学なら
            if grade <= 2023:
                categories.update({
                    "社会人力養成科目":[[0,0]]
                })
            # 2024年度以降入学なら
            if grade >= 2024:
                categories.update({
                    "SDGs入門":[[0,0]]
                })

            # 学部ごとの処理
            # 総理
            if faculty == "engineering":
                if grade <= 2024:
                    categories.update({
                        "自然科学系学部共通科目":[[0,0]],
                        "基盤科目":[[0,0]],
                        "専門必修/専門選択/専門自由科目":[[0,0]]
                    })
                # 総合理工学科の場合
                elif grade >= 2025:
                    categories.update({
                        "理工共通基礎科目":[[0,0]],
                        "理工社会実装教育科目":[[0,0]],
                        "専門人材教育科目":[[0,0]]
                    })

            # 材料エネルギー学部
            if faculty == "material":
                categories.update({
                    "基盤科目":[[0,0]],
                    "専門必修/専門選択科目":[[0,0]]
                    })
                if grade >= 2024:
                    del categories["健康・スポーツ/文化・芸術等"]

                        #   "基盤科目(生資)":[0],
                        #   "自然科学系学部共通科目(生資)":[0],
                        #   "専門科目(法文)":[0],
                        #   "専門科目(人間)":[0],
                        #   "専門共通科目(教育)":[0],
                        #   "教育体験活動":[0],
                        #   "専門科目(教育)":[0],
                        #   "大学院":[0]

            # 共通
            categories.update({
                "全学開放科目":[[0,0]],
                "教職・学芸員":[[0,0]],
                "分類漏れ":[[0,0]]
            })
            
            for _, row in df_passed.iterrows():
                code = str(row["時間割コード"])
                name = row["開講科目"]
                year = str(row["開講年度"])
                credit = get_credit(year,code)
                category = classify(code,faculty,grade)
                if credit[0] != None:
                    categories.setdefault(category)[0][0] += credit[0]
                else: categories.setdefault(category)[0][1] = 1
                categories.setdefault(category, []).append([name,credit[0],credit[1],code])
                num += 1
                if credit[1] != 1:
                    no_credit.append(name) 

            if no_credit:
                show_message = True

            result = categories

    return render_template("result.html", result=result,no_credit=no_credit,show_message=show_message,num=num)

if __name__ == "__main__":
    app.run(debug=True) # 開発用サーバをデバックモードで実行