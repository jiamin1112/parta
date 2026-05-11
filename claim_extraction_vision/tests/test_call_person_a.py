import requests


def call_person_a(text=None, url=None, language="zh", source_type="news"):
    api_url = "http://127.0.0.1:8000/extract_claims"
    payload = {
        "text": text,
        "url": url,
        "language": language,
        "source_type": source_type,
    }
    response = requests.post(api_url, json=payload)
    response.raise_for_status()
    data = response.json()
    return data["next_module_input"]["claims"]


if __name__ == "__main__":
    claims = call_person_a(
        text="这一季的《乘风》，早就被剧本牢牢套死，所有流程都是按部就班在演戏。  再也没有初舞台的惊艳，也没有一公直播的热血，只剩下满满的疲惫感。  明明开播前，节目组把“全程直播、全开麦真实竞技”当成最大卖点。  靠着零修音、直面实力审判的噱头，狠狠收割了一大波关注度。  初舞台刷屏全网，一公话题不断，热度和讨论度双双拉满。  所有人都以为，这一季终于回归实力比拼，能重现前几季的高光时刻。  可谁也没想到，仅仅来到二公上半场，热度就断崖式下跌。  直播数据冷清，热搜话题平淡，网友讨论寥寥无几，完全撑不起场面。",
        url=None,
        language="zh",
        source_type="news",
    )
    print("人员 A 输出 claims：")
    for item in claims:
        print(f'{item["id"]}. [{item["type"]}] {item["claim"]} confidence={item["confidence"]}')
