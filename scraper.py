import urllib.request
import re
import html

def fetch_requests():
    url = "https://khamsat.com/community/requests"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        page_html = resp.read().decode("utf-8")

    blocks = re.findall(r'<td class="details-td">(.*?)</td>', page_html, re.DOTALL)
    items = []
    for b in blocks:
        title_match = re.search(r'<h3 class="details-head"><a[^>]*href="([^"]+)"[^>]*>(.*?)</a></h3>', b)
        if not title_match:
            continue
        href = title_match.group(1)
        title = html.unescape(title_match.group(2).strip())
        
        user_match = re.search(r'<a class="user"[^>]*>(.*?)</a>', b)
        user_name = "مستخدم"
        if user_match:
            clean_user = re.sub(r'<[^>]+>', '', user_match.group(1)).strip()
            if clean_user:
                user_name = html.unescape(clean_user)

        time_match = re.search(r'<span[^>]*dir="ltr"[^>]*>(.*?)</span>', b, re.DOTALL)
        post_time = ""
        if time_match:
            post_time = " ".join(time_match.group(1).split())
            post_time = html.unescape(post_time)

        id_match = re.search(r'/requests/(\d+)', href)
        post_id = int(id_match.group(1)) if id_match else 0

        full_link = f"https://khamsat.com{href}"
        items.append({
            "id": post_id,
            "title": title,
            "user": user_name,
            "time": post_time,
            "url": full_link
        })
    return items

if __name__ == "__main__":
    results = fetch_requests()
    for item in results[:5]:
        print(f"[{item['id']}] {item['title']} | {item['user']} | {item['time']}")
        print(f"URL: {item['url']}\n")
