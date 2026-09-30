#!/usr/bin/env python3
"""Build a standalone static blog for GitHub Pages from the 每日要闻综述 Blogger feed.

- Fetches the full Atom feed (paginated).
- Generates site/index.html (home + monthly archive) and site/<pid>.html (articles).
- Articles carry <link rel="canonical"> pointing at the Blogger original.
- Design matches the minimalist personal site (inline CSS + theme toggle).
Idempotent: regenerates everything from the feed each run.
"""
import html as htmlmod
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = BASE
FEED_BASE = "https://blog.ltshijie.dpdns.org/feeds/posts/default"
PAGES_URL = "https://shengfeng2019.github.io/blog/"
BJ = ZoneInfo("Asia/Shanghai")
UA = {"User-Agent": "Mozilla/5.0 (github-blog-build)"}
PAGE_SIZE = 150
MAX_POSTS = 2000
LATEST_COUNT = 10
BLOG_NAME = "每日要闻综述"
BLOG_DESC = "每日精选全球及中国财经、时事热点新闻，帮您一站式快速掌握市场脉搏。"

NS = {"a": "http://www.w3.org/2005/Atom"}


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def fetch_all_posts():
    posts = []
    start = 1
    while len(posts) < MAX_POSTS:
        url = f"{FEED_BASE}?max-results={PAGE_SIZE}&start-index={start}"
        data = fetch(url)
        root = ET.fromstring(data)
        entries = root.findall("a:entry", NS)
        if not entries:
            break
        for e in entries:
            eid = (e.findtext("a:id", default="", namespaces=NS) or "").strip()
            m = re.search(r"post-(\d+)", eid)
            if not m:
                continue
            pid = m.group(1)
            title = (e.findtext("a:title", default="", namespaces=NS) or "").strip()
            pub = (e.findtext("a:published", default="", namespaces=NS) or "").strip()
            content_el = e.find("a:content", NS)
            content = content_el.text if content_el is not None and content_el.text else ""
            link = ""
            for l in e.findall("a:link", NS):
                if l.get("rel", "alternate") == "alternate":
                    link = l.get("href", "") or ""
                    break
            posts.append({"pid": pid, "title": title, "published": pub,
                          "content": content, "link": link})
        if len(entries) < PAGE_SIZE:
            break
        start += PAGE_SIZE
    return posts


def fmt_date_long(pub):
    try:
        dt = datetime.fromisoformat(pub).astimezone(BJ)
        return f"{dt.year}年{dt.month}月{dt.day}日"
    except Exception:
        return pub[:10]


def fmt_date_short(pub):
    try:
        dt = datetime.fromisoformat(pub).astimezone(BJ)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return pub[:10]


def month_key(pub):
    try:
        dt = datetime.fromisoformat(pub).astimezone(BJ)
        return f"{dt.year}年{dt.month}月"
    except Exception:
        return pub[:7]


def sanitize(content):
    s = re.sub(r"<script\b[^>]*>.*?</script\s*>", "", content, flags=re.I | re.S)
    s = re.sub(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", "", s, flags=re.I)
    s = re.sub(r"href\s*=\s*(\"|')\s*javascript:[^\"']*\1", 'href="#"', s, flags=re.I)
    return s


def excerpt(content, n=140):
    text = re.sub(r"<[^>]+>", " ", content)
    text = htmlmod.unescape(re.sub(r"\s+", " ", text)).strip()
    return text[:n] + ("…" if len(text) > n else "")


CSS_BUNDLE = r"""
  :root{
    --bg:#fafaf9; --fg:#161616; --muted:#6f6f6f; --hair:rgba(0,0,0,.1);
    --card:#ffffff; --accent:#161616;
  }
  [data-theme="dark"]{
    --bg:#0d0d0d; --fg:#ededed; --muted:#9a9a9a; --hair:rgba(255,255,255,.12);
    --card:#141414; --accent:#ededed;
  }
  @media (prefers-color-scheme: dark){
    [data-theme="auto"]{
      --bg:#0d0d0d; --fg:#ededed; --muted:#9a9a9a; --hair:rgba(255,255,255,.12);
      --card:#141414; --accent:#ededed;
    }
  }
  *{margin:0;padding:0;box-sizing:border-box}
  html{scroll-behavior:smooth}
  body{
    background:var(--bg); color:var(--fg);
    font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei","Segoe UI",sans-serif;
    -webkit-font-smoothing:antialiased; line-height:1.7;
    transition:background .3s ease,color .3s ease;
  }
  .wrap{max-width:720px;margin:0 auto;padding:0 24px}
  /* nav */
  nav{position:sticky;top:0;z-index:10;background:color-mix(in srgb,var(--bg) 88%,transparent);
    backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border-bottom:1px solid var(--hair)}
  nav .wrap{display:flex;align-items:center;justify-content:space-between;height:60px}
  .brand{font-weight:700;letter-spacing:.06em;font-size:15px;text-decoration:none;color:var(--fg)}
  .links{display:flex;gap:22px;align-items:center}
  .links a{font-size:14px;color:var(--muted);text-decoration:none;transition:color .2s}
  .links a:hover{color:var(--fg)}
  #themeBtn{background:none;border:1px solid var(--hair);border-radius:999px;width:34px;height:34px;
    cursor:pointer;color:var(--fg);font-size:15px;line-height:1;display:flex;align-items:center;justify-content:center}
  /* hero */
  .hero{padding:clamp(72px,14vw,140px) 0 clamp(48px,8vw,84px)}
  .hero .kicker{font-size:13px;letter-spacing:.28em;color:var(--muted);margin-bottom:22px}
  .hero h1{font-size:clamp(44px,10vw,84px);line-height:1.12;font-weight:800;letter-spacing:.02em}
  .hero h1 .en{display:block;font-family:Georgia,"Times New Roman",serif;font-weight:400;
    font-style:italic;font-size:.42em;letter-spacing:.04em;color:var(--muted);margin-top:10px}
  .hero p.lead{margin-top:26px;font-size:clamp(16px,2.6vw,19px);color:var(--muted);max-width:34em}
  /* sections */
  section{padding:clamp(40px,7vw,72px) 0;border-top:1px solid var(--hair)}
  .sec-head{display:flex;align-items:baseline;gap:14px;margin-bottom:28px}
  .sec-num{font-family:Georgia,serif;font-style:italic;color:var(--muted);font-size:15px}
  .sec-head h2{font-size:clamp(22px,4vw,28px);font-weight:700;letter-spacing:.08em}
  .about p{color:var(--muted);font-size:16px;max-width:38em}
  .about p+p{margin-top:16px}
  .about strong{color:var(--fg);font-weight:600}
  /* works */
  .works{display:grid;gap:16px}
  @media(min-width:560px){.works{grid-template-columns:1fr 1fr 1fr}}
  .work{background:var(--card);border:1px solid var(--hair);border-radius:14px;padding:28px 22px;
    min-height:190px;display:flex;flex-direction:column;justify-content:space-between;
    transition:transform .25s ease,box-shadow .25s ease}
  .work:hover{transform:translateY(-4px)}
  .work .tag{font-size:12px;letter-spacing:.2em;color:var(--muted)}
  .work h3{font-size:18px;margin:12px 0 8px;font-weight:700}
  .work p{font-size:14px;color:var(--muted)}
  .work.soon{border-style:dashed;align-items:flex-start}
  .work.soon .dot{width:8px;height:8px;border-radius:50%;background:var(--muted);opacity:.5;margin-bottom:14px}
  /* blog */
  .blog-list{display:flex;flex-direction:column}
  .post-item{display:flex;gap:18px;align-items:baseline;padding:15px 4px;border-bottom:1px solid var(--hair);
    text-decoration:none;color:var(--fg);transition:padding .2s ease}
  .post-item:hover{padding-left:12px}
  .post-item .post-date{flex:none;font-size:13px;color:var(--muted);font-variant-numeric:tabular-nums;min-width:96px}
  .post-item .post-title{font-size:16px;font-weight:600;line-height:1.5}
  .blog-more{margin-top:22px}
  .blog-more a{font-size:14px;color:var(--muted);text-decoration:none}
  .blog-more a:hover{color:var(--fg)}
  /* contact */
  .contact-big{display:block;font-size:clamp(20px,4.6vw,30px);font-weight:700;color:var(--fg);
    text-decoration:none;margin:6px 0 20px;word-break:break-all}
  .contact-big:hover{text-decoration:underline;text-underline-offset:6px}
  .contact p{color:var(--muted);font-size:15px;max-width:36em}
  .socials{display:flex;gap:12px;margin-top:26px;flex-wrap:wrap}
  .socials a{font-size:14px;color:var(--fg);text-decoration:none;border:1px solid var(--hair);
    border-radius:999px;padding:9px 20px;transition:background .2s,color .2s}
  .socials a:hover{background:var(--fg);color:var(--bg)}
  footer{border-top:1px solid var(--hair);padding:28px 0 40px;color:var(--muted);font-size:13px}
  footer .wrap{display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px}

  .article{padding:clamp(40px,7vw,72px) 0}
  .article .kicker{font-size:13px;letter-spacing:.28em;color:var(--muted);margin-bottom:18px}
  .article h1{font-size:clamp(26px,5vw,38px);line-height:1.35;font-weight:800;letter-spacing:.01em}
  .article .meta{margin-top:14px;font-size:13px;color:var(--muted)}
  .article .meta a{color:var(--muted)}
  .post-body{margin-top:34px;font-size:16px;color:var(--fg);overflow-wrap:break-word}
  .post-body p{margin:1em 0}
  .post-body img{max-width:100%;height:auto;border-radius:10px;margin:1.2em 0}
  .post-body a{color:var(--fg);text-underline-offset:4px}
  .post-body blockquote{border-left:3px solid var(--hair);margin:1.2em 0;padding:.4em 0 .4em 1em;color:var(--muted)}
  .post-body pre{background:var(--card);border:1px solid var(--hair);border-radius:10px;
    padding:14px;overflow:auto;font-size:13px}
  .post-body table{border-collapse:collapse;width:100%;margin:1.2em 0;font-size:14px}
  .post-body th,.post-body td{border:1px solid var(--hair);padding:8px 10px;text-align:left}
  .post-body h2,.post-body h3{margin:1.4em 0 .6em;line-height:1.4}
  .back{margin-top:44px;font-size:14px}
  .back a{color:var(--muted);text-decoration:none}
  .back a:hover{color:var(--fg)}
  .archive-month{margin:34px 0 14px;font-size:15px;font-weight:700;letter-spacing:.12em;color:var(--muted)}
  .hero{padding:clamp(48px,8vw,84px) 0 8px}
  .hero h1{font-size:clamp(30px,6vw,44px);font-weight:800;letter-spacing:.02em}
  .hero p{margin-top:12px;color:var(--muted);font-size:15px;max-width:38em;line-height:1.8}

"""


def shared_css():
    return CSS_BUNDLE


def nav_html():
    return """<nav>
  <div class="wrap">
    <a class="brand" href="/">""" + BLOG_NAME + """</a>
    <div class="links">
      <a href="/">首页</a>
      <button id="themeBtn" aria-label="切换深色/浅色" title="切换深色/浅色">◐</button>
    </div>
  </div>
</nav>"""


FOOTER_HTML = """<footer>
  <div class="wrap">
    <span>© 2026 王升锋 · 每日要闻综述</span>
    <span>Hosted on GitHub Pages</span>
  </div>
</footer>"""

THEME_JS = """<script>
(function(){
  var root=document.documentElement, btn=document.getElementById('themeBtn');
  try{
    var saved=localStorage.getItem('theme');
    if(saved==='light'||saved==='dark') root.setAttribute('data-theme',saved);
  }catch(e){}
  function syncIcon(){
    var t=root.getAttribute('data-theme');
    var dark = t==='dark' || (t==='auto' && matchMedia('(prefers-color-scheme: dark)').matches);
    btn.textContent = dark ? '◑' : '◐';
  }
  btn.addEventListener('click',function(){
    var t=root.getAttribute('data-theme');
    var dark = t==='dark' || (t==='auto' && matchMedia('(prefers-color-scheme: dark)').matches);
    var next = dark ? 'light' : 'dark';
    root.setAttribute('data-theme',next);
    try{localStorage.setItem('theme',next);}catch(e){}
    syncIcon();
  });
  syncIcon();
})();
</script>"""


def write_css():
    with open(os.path.join(OUT_DIR, "style.css"), "w",
              encoding="utf-8") as f:
        f.write(shared_css())


def page_shell(title, desc, body_html, canonical=""):
    canon = (f'<link rel="canonical" href="{htmlmod.escape(canonical, quote=True)}">'
             if canonical else "")
    return f"""<!DOCTYPE html>
<html lang="zh-CN" data-theme="auto">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{htmlmod.escape(title)}</title>
<meta name="description" content="{htmlmod.escape(desc)}">
{canon}
<link rel="stylesheet" href="/style.css">
</head>
<body>
{nav_html()}
<main class="wrap">
{body_html}
</main>
{FOOTER_HTML}
{THEME_JS}
</body>
</html>
"""


def post_item(p):
    return ('<a class="post-item" href="/{}.html">'
            '<span class="post-date">{}</span>'
            '<span class="post-title">{}</span></a>').format(
                p["pid"], fmt_date_short(p["published"]),
                htmlmod.escape(p["title"]))


def write_article(post):
    body = f"""<article class="article">
  <div class="kicker">每日要闻综述</div>
  <h1>{htmlmod.escape(post['title'])}</h1>
  <div class="meta">{fmt_date_long(post['published'])} · <a href="{htmlmod.escape(post['link'])}" target="_blank" rel="noopener">阅读原文</a></div>
  <div class="post-body">
{sanitize(post['content'])}
  </div>
  <p class="back"><a href="/">← 返回首页</a></p>
</article>"""
    out = page_shell(post["title"] + " · " + BLOG_NAME,
                     excerpt(post["content"], 120), body,
                     canonical=post["link"])
    with open(os.path.join(OUT_DIR, f"{post['pid']}.html"), "w",
              encoding="utf-8") as f:
        f.write(out)


def write_home(posts):
    parts = [f"""<div class="hero">
  <h1>{BLOG_NAME}</h1>
  <p>{BLOG_DESC}</p>
</div>
<div class="article" style="padding-top:24px">
  <div class="kicker">最新文章</div>
  <div class="blog-list">"""]
    for p in posts[:LATEST_COUNT]:
        parts.append("    " + post_item(p))
    parts.append("  </div>")
    parts.append(f'  <div class="kicker" style="margin-top:40px">全部文章 · 共 {len(posts)} 篇</div>')
    last_month = None
    for p in posts:
        mk = month_key(p["published"])
        if mk != last_month:
            if last_month is not None:
                parts.append("  </div>")
            parts.append(f'  <div class="archive-month">{mk}</div>\n  <div class="blog-list">')
            last_month = mk
        parts.append("    " + post_item(p))
    parts.append("  </div>")
    parts.append("</div>")
    out = page_shell(BLOG_NAME, BLOG_DESC, "\n".join(parts),
                     canonical=PAGES_URL)
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(out)


def write_readme(n):
    readme = f"""# 每日要闻综述 · GitHub Pages 静态博客

{BLOG_DESC}

- 线上地址：{PAGES_URL}
- 内容来源：Blogger「{BLOG_NAME}」(https://blog.ltshijie.dpdns.org)，共 {n} 篇文章
- 构建脚本：`build.py`（GitHub Actions 每日 17:00 北京时间自动运行）

文章页均带有 canonical 指向 Blogger 原文。
"""
    with open(os.path.join(BASE, "README.md"), "w", encoding="utf-8") as f:
        f.write(readme)


def main():
    posts = fetch_all_posts()
    posts.sort(key=lambda p: p["published"], reverse=True)
    os.makedirs(OUT_DIR, exist_ok=True)
    write_css()
    for p in posts:
        write_article(p)
    write_home(posts)
    write_readme(len(posts))
    print(f"BUILD_OK posts={len(posts)}")


if __name__ == "__main__":
    main()
