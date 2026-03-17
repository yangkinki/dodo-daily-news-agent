import feedparser
import requests
import os
from datetime import datetime, timedelta

# 配置
SCT_KEY = os.environ["SCT_KEY"]
# GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")  # 可选

# 专题配置：名称 -> RSS源
TOPICS = {
    "AI前沿": "https://rsshub.app/leiphone/tag/人工智能",
    "科技动态": "https://rsshub.app/techcrunch",
    "财经要闻": "https://rsshub.app/wsj/latest"
}

'''
def get_ai_summary(text):
    """使用 Gemini 生成总结（可选）"""
    if not GEMINI_API_KEY or not text:
        return "（AI总结暂不可用）"
    try:
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
            json={
                "contents": [{
                    "parts": [{"text": f"用中文一句话总结以下内容，并分析其行业影响：{text[:2000]}"}]
                }]
            }
        )
        return resp.json()['candidates'][0]['content']['parts'][0]['text'].strip()
    except:
        return "（AI总结失败）"
'''

def fetch_news():
    content_lines = []
    yesterday = datetime.now() - timedelta(days=1)
    
    for topic, url in TOPICS.items():
        feed = feedparser.parse(url)
        items = []
        for entry in feed.entries[:2]:  # 每专题取2条
            pub_time = datetime(*entry.published_parsed[:6]) if entry.get('published_parsed') else datetime.now()
            if pub_time > yesterday:
                title = entry.title.replace("\n", " ")
                summary = entry.get('summary', '')[:300] or "暂无摘要"
                link = entry.link
        #        ai_summary = get_ai_summary(summary) if GEMINI_API_KEY else "（未启用AI总结）"
                
                items.append(
                    f"🔹 **【{topic}】**\n"
                    f"**标题**：{title}\n"
                    f"**摘要**：{summary}\n"
         #           f"**AI总结**：{ai_summary}\n"
                    f"👉 [查看详情]({link})\n"
                )
        if items:
            content_lines.append("\n".join(items))
    
    return "\n---\n".join(content_lines)

def send_to_wechat(content):
    if not content.strip():
        print("⚠️ 无新资讯")
        return
    resp = requests.post(
        f"https://sctapi.ftqq.com/{SCT_KEY}.send",
        data={
            "title": f"【AI·科技·财经晨报 | {datetime.now().strftime('%Y-%m-%d')}】",
            "desp": content
        }
    )
    print("✅ 推送成功" if resp.json().get("errno") == 0 else "❌ 推送失败")

if __name__ == "__main__":
    news = fetch_news()
    send_to_wechat(news)
