import requests

# ====================== 🔧 配置区（只改这里） ======================
SERVER_SEND_KEY = "SCT324116TIArqolxPpqN9XSWYnChrInaw"
DOUBAO_API_KEY  = "1f9b33cd-9bd6-4206-8336-70f4fdf7c19e"

# 中英文 6 大板块（权威国内外媒体）
SECTIONS = [
    {"name": "🌏 World News 国际", "rss": "https://rsshub.app/reuters/world"},
    {"name": "💰 Finance 财经",     "rss": "https://rsshub.app/wsj/markets"},
    {"name": "🏙 Society 社会",     "rss": "https://rsshub.app/people/daily-news-society"},
    {"name": "🤖 AI & Tech AI",     "rss": "https://rsshub.app/36kr/search/AI"},
    {"name": "🚀 Science & Tech 科技", "rss": "https://rsshub.app/mitreview/latest"},
    {"name": "🧘 Health 健康",       "rss": "https://rsshub.app/webmd/news"},
]
# ==================================================================

def get_rss_items(url, limit=3):
    try:
        resp = requests.get(url, timeout=15)
        return resp.json()["items"][:limit]
    except:
        return []

def ai_summarize(title, content):
    prompt = f"""请用简洁、客观、通顺的中文一句话总结这篇新闻（25字内）：
标题：{title}
内容：{content}"""
    try:
        r = requests.post(
            url="https://ark.cn-beijing.volces.com/api/v3/chat/completions",
            headers={"Authorization": f"Bearer {DOUBAO_API_KEY}"},
            json={
                "model": "doubao-1-pro",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2
            },
            timeout=10
        )
        return r.json()["choices"][0]["message"]["content"].strip()
    except:
        return title

def build_markdown():
    lines = ["# 🌅 Your Daily Smart News 智能早报\n"]
    
    for sec in SECTIONS:
        lines.append(f"## {sec['name']}")
        items = get_rss_items(sec["rss"], 3)
        if not items:
            lines.append("No news today.\n")
            continue
        
        for i, item in enumerate(items, 1):
            title = item["title"]
            link  = item["url"]
            summary = ai_summarize(title, item.get("summary", ""))
            lines.append(f"{i}. **[{title}]({link})**")
            lines.append(f"   {summary}\n")
        
        lines.append("---")
    
    lines.append("✅ Stay informed, stay healthy.")
    return "\n".join(lines)

def send_to_wechat(content):
    api = f"https://sct.ftqq.com/{SERVER_SEND_KEY}.send"
    requests.post(api, data={
        "title": "🌅 智能双语早报",
        "desp": content
    })

if __name__ == "__main__":
    report = build_markdown()
    send_to_wechat(report)