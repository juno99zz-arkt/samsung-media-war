# -*- coding: utf-8 -*-
"""
Samsung vs Union Media War — Static HTML Generator
GitHub Actions에서 실행: 뉴스/유튜브 수집 → 분류 → 요약 → docs/index.html 생성
"""
import feedparser, re, urllib.parse, json, os, anthropic
from datetime import datetime, timedelta

# ── 설정 ─────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
DOCS_DIR   = os.path.join(os.path.dirname(__file__), 'docs')
TREND_FILE = os.path.join(DOCS_DIR, 'trend.json')
OUT_FILE   = os.path.join(DOCS_DIR, 'index.html')
os.makedirs(DOCS_DIR, exist_ok=True)

# ── 주제 키워드 ──────────────────────────────────────────────────
TOPIC_MUST  = ['삼성', 'samsung']
TOPIC_UNION = ['노조','파업','조합원','단협','단체교섭','노동자','근로자',
               '임금','쟁의','전삼노','삼성전자노조',
               'union','strike','worker','labor','labour','walkout']

SAMSUNG_SIGNALS = [
    '불법파업','위법파업','불법 파업','위법 파업','업무방해','조업방해','생산방해',
    '파업 강행','강행 파업','총파업 강행','파업 장기화','상습 파업',
    '파업 반발','총파업 반발','파업에 반발','총파업에 반발','노조에 반발','파업 반대',
    '반발 확산','반발 거세','공개 반발','강하게 반발',
    '주주 반발','주주 반대','주주 비판',
    '손배소','손해배상 청구','손해배상 소송','가처분 신청','가처분 결정',
    '법적절차 돌입','법적 대응 착수','법적 조치',
    '직권중재 발동','직권중재 촉구','직권중재 요청','긴급조정권 발동 촉구',
    '내홍','노조 내홍','탈퇴 러시','탈퇴 행렬','노조 탈퇴','조합원 이탈','노조 분열',
    '자본충실원칙 위배','상법상 위배','노조 주장 기각','법원 결정','법원 명령',
    '생산차질','생산 차질','공장 가동','조업 정상화','생산 재개',
    '100조 피해','조 피해','파업 피해','주주단체','소액주주','경영권 수호',
    '전유물 아냐','전유물 아니','전유물이 아냐','전유물이 아니',
    '파업 상상 못','상상 못 할','파업 있을 수 없','파업 불가',
    '헛소리','말도 안 돼',
    'illegal strike','illegal walkout','production disruption',
    'court order','injunction','damage claim','damage lawsuit',
    'back to work','return to work','resume production',
    'unauthorized strike','union internal conflict','breach of trust','risk breach',
]

UNION_SIGNALS = [
    '부당노동행위','노조 탄압','노동권 탄압','노동권 침해',
    '단체교섭 거부','교섭 거부','협상 거부','성과급 차별','임금 차별','임금차별',
    '성과급 불공정','갑질','착취','부당 해고','보복 인사','노조 활동 방해','노조 설립 방해',
    '노동자 권리','노동권 보장','파업 지지','파업 정당','합법 파업','정당한 파업','노동자 연대',
    '삼성 규탄','삼성 비판',
    # ↓ 중립 사실 용어 제거: 파업예고/협상결렬은 논조와 무관한 팩트
    '파업권','파업은 권리','파업 권리','헌법상 권리','헌법적 권리',
    '긴급조정권 반대','긴급조정권 발동 반대','긴급조정권 본질','긴급조정권 왜곡',
    '긴급조정권 신중','조정권 신중','직권중재 반대','강제조정 반대','강제 조정 안',
    '파업조정권 신중','긴급조정 남용','조정권 남용',
    '민주노총',
    "workers' rights",'unfair labor practice','union busting',
    'worker exploitation','solidarity','labor rights',
    'samsung criticized','samsung condemned','samsung refuses',
    'collective bargaining refused','wage discrimination','unfair dismissal',
    'demands bigger bonus','demands share','workers demand','employees demand',
]

FALLBACK_S = ['강행','불법','방해','차질','내홍','이탈','손배','위법','반발','전유물 아','illegal','refuse','disruption']
FALLBACK_U = ['탄압','착취','갑질','차별','부당','침해','파업권','헌법','busting','exploitation']

# ── RSS 피드 ─────────────────────────────────────────────────────
def _enc(q): return urllib.parse.quote(q)

RSS_FEEDS = [
    f'https://news.google.com/rss/search?q={_enc("삼성 노조 파업")}&hl=ko&gl=KR&ceid=KR:ko',
    f'https://news.google.com/rss/search?q={_enc("삼성전자 노조")}&hl=ko&gl=KR&ceid=KR:ko',
    f'https://news.google.com/rss/search?q={_enc("삼성 전삼노")}&hl=ko&gl=KR&ceid=KR:ko',
    f'https://news.google.com/rss/search?q={_enc("삼성전자 파업 임금")}&hl=ko&gl=KR&ceid=KR:ko',
    f'https://news.google.com/rss/search?q={_enc("삼성 노사 임금인상")}&hl=ko&gl=KR&ceid=KR:ko',
    f'https://news.google.com/rss/search?q={_enc("삼성전자 단체교섭")}&hl=ko&gl=KR&ceid=KR:ko',
    f'https://news.google.com/rss/search?q={_enc("Samsung union strike")}&hl=en&gl=US&ceid=US:en',
    f'https://news.google.com/rss/search?q={_enc("Samsung labor union 2026")}&hl=en&gl=US&ceid=US:en',
    f'https://news.google.com/rss/search?q={_enc("Samsung Electronics workers strike")}&hl=en&gl=US&ceid=US:en',
    'https://www.yna.co.kr/rss/news.xml',
    'https://www.hani.co.kr/rss/',
    'https://www.khan.co.kr/rss/rssdata/total_news.xml',
    'https://www.ohmynews.com/NWS_Web/Rss/livernews.aspx',
    'https://www.nocutnews.co.kr/rss/allnews.xml',
    'https://www.hankyung.com/feed/all-news',
    'https://rss.mt.co.kr/mt_news.xml',
    f'https://news.google.com/rss/search?q={_enc("삼성 노조 탄압")}&hl=ko&gl=KR&ceid=KR:ko',
    f'https://news.google.com/rss/search?q={_enc("삼성전자 성과급 차별")}&hl=ko&gl=KR&ceid=KR:ko',
    f'https://news.google.com/rss/search?q={_enc("삼성 노동자 권리")}&hl=ko&gl=KR&ceid=KR:ko',
]

TIMELINE_FEEDS = [
    f'https://news.google.com/rss/search?q={_enc("삼성전자 노조 파업 after:2026-02-01")}&hl=ko&gl=KR&ceid=KR:ko',
    f'https://news.google.com/rss/search?q={_enc("삼성전자 전삼노 파업 after:2026-02-01")}&hl=ko&gl=KR&ceid=KR:ko',
    f'https://news.google.com/rss/search?q={_enc("삼성전자 노사 임금협상 after:2026-02-01")}&hl=ko&gl=KR&ceid=KR:ko',
    f'https://news.google.com/rss/search?q={_enc("삼성전자 파업 긴급조정 after:2026-02-01")}&hl=ko&gl=KR&ceid=KR:ko',
    f'https://news.google.com/rss/search?q={_enc("삼성전자 노조 손배소 after:2026-02-01")}&hl=ko&gl=KR&ceid=KR:ko',
    f'https://news.google.com/rss/search?q={_enc("삼성전자 파업 단체교섭 after:2026-02-01")}&hl=ko&gl=KR&ceid=KR:ko',
    f'https://news.google.com/rss/search?q={_enc("삼성전자 노조 탈퇴 내홍 after:2026-02-01")}&hl=ko&gl=KR&ceid=KR:ko',
    f'https://news.google.com/rss/search?q={_enc("Samsung Electronics union strike 2026")}&hl=en&gl=US&ceid=US:en',
    f'https://news.google.com/rss/search?q={_enc("Samsung union walkout labor 2026")}&hl=en&gl=US&ceid=US:en',
]

YT_QUERIES = [
    '삼성전자 노조 파업 2026',
    '전삼노 파업 삼성전자',
    '삼성 노조 불법파업',
    '삼성 노동자 파업권',
    'Samsung Electronics union strike 2026',
]

# ── 유틸 ─────────────────────────────────────────────────────────
def strip_html(text):
    text = re.sub(r'<[^>]+>', ' ', text or '')
    return re.sub(r'\s+', ' ', text).strip()

def is_relevant(text):
    t = text.lower()
    return any(k in t for k in TOPIC_MUST) and any(k in t for k in TOPIC_UNION)

def score(text):
    t = text.lower()
    return (sum(1 for k in SAMSUNG_SIGNALS if k in t),
            sum(1 for k in UNION_SIGNALS   if k in t))

def clean_source(src):
    src = re.sub(r'\s*-\s*(Google 뉴스|Google News).*', '', src or '').strip()
    return src or '기타'

def extract_source(raw_title, feed_title):
    """Google News 제목 끝 '- 언론사명' 패턴으로 언론사 추출; 직접 RSS는 feed_title 사용"""
    m = re.search(r'\s+-\s+([^-\n]{2,25})$', raw_title.strip())
    if m:
        candidate = m.group(1).strip()
        if not re.match(r'^\d', candidate):   # 날짜 형식 제외
            return candidate
    return clean_source(feed_title)

# ── 기사 수집 ────────────────────────────────────────────────────
def fetch_articles():
    cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    seen, arts = set(), []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
            feed_title = feed.feed.get('title', '')
            for e in feed.entries[:50]:
                link = e.get('link', '')
                if link in seen: continue
                seen.add(link)
                try:    pub = datetime(*e.published_parsed[:6])
                except: pub = datetime.now()
                if pub < cutoff: continue
                raw_title = strip_html(e.get('title', ''))
                # 언론사명을 제목에서 분리: "제목 - 언론사명" → (제목, 언론사)
                m = re.search(r'^(.+?)\s+-\s+([^-]{2,25})$', raw_title)
                if m:
                    title  = m.group(1).strip()
                    source = m.group(2).strip()
                else:
                    title  = raw_title
                    source = clean_source(feed_title)
                summary = strip_html(e.get('summary', ''))
                full    = title + ' ' + summary
                if not is_relevant(full): continue
                arts.append({'title': title, 'link': link, 'summary': summary[:280],
                             'published': pub.strftime('%Y-%m-%d %H:%M'),
                             'source': source,
                             '_pub_dt': pub, '_text': full})
        except Exception as ex:
            print(f'[RSS] {url[:55]}: {ex}')
    return arts

def fetch_timeline_articles():
    cutoff = datetime(2026, 2, 1)
    seen, arts = set(), []
    for url in TIMELINE_FEEDS:
        try:
            feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
            for e in feed.entries[:100]:
                link = e.get('link', '')
                if link in seen: continue
                seen.add(link)
                try:    pub = datetime(*e.published_parsed[:6])
                except: pub = datetime.now()
                if pub < cutoff: continue
                title = strip_html(e.get('title', ''))
                full  = title + ' ' + strip_html(e.get('summary', ''))
                if not is_relevant(full): continue
                arts.append({'title': title, 'published': pub.strftime('%Y-%m-%d'), '_pub_dt': pub})
        except Exception as ex:
            print(f'[TL RSS] {url[:55]}: {ex}')
    arts.sort(key=lambda a: a['_pub_dt'])
    return arts

# ── 전삼노 홈페이지 ──────────────────────────────────────────────
def fetch_jeonsamno():
    try:
        import requests
        from bs4 import BeautifulSoup
        url = 'https://samsunglabor.co.kr/bbs/board.php?bo_table=bodo'
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        posts = []
        # gnuboard5 표준 구조
        for row in soup.select('#fboardlist tbody tr'):
            title_el = row.select_one('.td_subject a, td.td_subject a')
            date_el  = row.select_one('.td_datetime, td.td_datetime')
            if not title_el: continue
            title = title_el.get_text(strip=True)
            if not title: continue
            date  = date_el.get_text(strip=True)[:10] if date_el else ''
            href  = title_el.get('href', '')
            if href and not href.startswith('http'):
                href = 'https://samsunglabor.co.kr' + href
            posts.append({'title': title, 'date': date, 'link': href})
        print(f'  전삼노 {len(posts)}건 수집')
        return posts[:25]
    except Exception as e:
        print(f'[전삼노] {e}')
        return []

# ── 유튜브 수집 (2026-02-01 이후, 조회수 기준) ──────────────────
YT_CUTOFF = '20260201'   # 2026년 2월 이후만 포함

def fetch_youtube_videos():
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        print('[YouTube] yt-dlp 없음, 스킵')
        return []

    ydl_opts = {
        'quiet': True, 'no_warnings': True,
        'extract_flat': True, 'skip_download': True,
    }
    seen, results = set(), []
    for q in YT_QUERIES:
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f'ytsearch30:{q}', download=False)
                for e in (info.get('entries') or []):
                    if not e: continue
                    vid_id = e.get('id', '')
                    if not vid_id or vid_id in seen: continue
                    seen.add(vid_id)
                    # 2026-02-01 이전 영상 제외
                    upload_raw = e.get('upload_date', '') or ''
                    if upload_raw and upload_raw < YT_CUTOFF: continue
                    title = e.get('title', '')
                    desc  = e.get('description', '') or ''
                    full  = title + ' ' + desc
                    if not any(k in full.lower() for k in ['삼성', 'samsung']): continue
                    upload_date = f'{upload_raw[:4]}-{upload_raw[4:6]}-{upload_raw[6:]}' if len(upload_raw)==8 else upload_raw
                    results.append({
                        'title':       title,
                        'url':         f'https://www.youtube.com/watch?v={vid_id}',
                        'thumbnail':   f'https://i.ytimg.com/vi/{vid_id}/mqdefault.jpg',
                        'view_count':  e.get('view_count') or 0,
                        'channel':     e.get('channel') or e.get('uploader', ''),
                        'upload_date': upload_date,
                        '_text': full,
                    })
        except Exception as ex:
            print(f'[YT] {q[:30]}: {ex}')
    # 조회수 내림차순 정렬 후 중복 없이 반환
    results.sort(key=lambda x: -(x['view_count'] or 0))
    print(f'  유튜브 {len(results)}건 수집 (2026-02~ 기준)')
    return results

# 편향 성향이 알려진 유튜브 채널 (채널명 substring 매칭)
YT_UNION_CH   = ['한겨레', '경향신문', '오마이뉴스', '민주노총', '뉴스타파', '참세상']
YT_SAMSUNG_CH = ['조선일보', '중앙일보', '동아일보', '매일경제', '한국경제', '연합뉴스tv', 'kbs']

def classify_youtube(videos):
    s_list, u_list = [], []
    for v in videos:
        # 제목만으로 분류 — description은 맥락 오염 위험이 높아 사용 안 함
        s, u = score(v['title'])
        if s == 0 and u == 0:
            ch = v.get('channel', '').lower()
            if   any(k in ch for k in YT_UNION_CH):   u = 1
            elif any(k in ch for k in YT_SAMSUNG_CH): s = 1
            else: continue   # 명확한 시그널 없으면 제외
        item = {k: val for k, val in v.items() if not k.startswith('_')}
        vc   = v.get('view_count', 0) or 0
        if   s > u: s_list.append((item, s, vc))
        elif u > s: u_list.append((item, u, vc))
        elif s > 0: s_list.append((item, s, vc)); u_list.append((item, u, vc))

    s_list.sort(key=lambda x: -x[2])   # 조회수 내림차순
    u_list.sort(key=lambda x: -x[2])

    def power(lst): return sum(sc for _, sc, _ in lst) + len(lst) * 3
    sp, up = power(s_list), power(u_list)
    total  = sp + up
    yt_s_pct = round(sp / total * 100) if total else 50
    return ([a for a, _, _ in s_list[:5]], [a for a, _, _ in u_list[:5]],
            len(s_list), len(u_list), yt_s_pct, 100 - yt_s_pct)

# ── 100일 언론사 편향 분석 ────────────────────────────────────────
def fetch_articles_100days():
    """최근 100일 기사 수집 (언론사 편향도 분석 전용)"""
    cutoff = datetime.now() - timedelta(days=100)
    seen, arts = set(), []
    all_feeds = list(TIMELINE_FEEDS) + list(RSS_FEEDS)
    for url in all_feeds:
        try:
            feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
            feed_title = feed.feed.get('title', '')
            for e in feed.entries[:100]:
                link = e.get('link', '')
                if link in seen: continue
                seen.add(link)
                try:    pub = datetime(*e.published_parsed[:6])
                except: pub = datetime.now()
                if pub < cutoff: continue
                raw_title = strip_html(e.get('title', ''))
                m = re.search(r'^(.+?)\s+-\s+([^-]{2,25})$', raw_title)
                if m:
                    title  = m.group(1).strip()
                    source = m.group(2).strip()
                else:
                    title  = raw_title
                    source = clean_source(feed_title)
                full = title + ' ' + strip_html(e.get('summary', ''))
                if not is_relevant(full): continue
                arts.append({'title': title, 'source': source, '_text': full})
        except: pass
    return arts

def compute_media_bias(articles):
    """기사 목록에서 언론사별 삼성/노조 우호 기사 수 집계"""
    s_src, u_src = {}, {}
    for art in articles:
        s, u = score(art['_text'])
        if s == 0 and u == 0:
            tl = art['title'].lower()
            if   any(k in tl for k in FALLBACK_S): s = 1
            elif any(k in tl for k in FALLBACK_U): u = 1
            else: continue
        src = art.get('source', '기타') or '기타'
        if   s > u: s_src[src] = s_src.get(src, 0) + 1
        elif u > s: u_src[src] = u_src.get(src, 0) + 1
        elif s > 0:
            s_src[src] = s_src.get(src, 0) + 1
            u_src[src] = u_src.get(src, 0) + 1
    s_media = sorted(s_src.items(), key=lambda x: -x[1])[:10]
    u_media = sorted(u_src.items(), key=lambda x: -x[1])[:10]
    return s_media, u_media

# ── 분류 ─────────────────────────────────────────────────────────
def classify(articles):
    s_list, u_list = [], []
    for art in articles:
        s, u = score(art['_text'])
        if s == 0 and u == 0:
            tl = art['title'].lower()
            if   any(k in tl for k in FALLBACK_S): s = 1
            elif any(k in tl for k in FALLBACK_U): u = 1
            else: continue
        a = {k: v for k, v in art.items() if not k.startswith('_')}
        if   s > u: s_list.append((a, s))
        elif u > s: u_list.append((a, u))
        elif s > 0: s_list.append((a, s)); u_list.append((a, u))

    s_list.sort(key=lambda x: -x[1])
    u_list.sort(key=lambda x: -x[1])
    top_s = [a for a, _ in s_list[:5]]
    top_u = [a for a, _ in u_list[:5]]

    def power(lst): return sum(sc for _, sc in lst) + len(lst) * 3
    sp, up = power(s_list), power(u_list)
    total  = sp + up
    s_pct  = round(sp / total * 100) if total else 50
    return top_s, top_u, s_pct, 100 - s_pct, len(s_list), len(u_list)

# ── Claude API ────────────────────────────────────────────────────
def ai_generate(recent_arts, tl_arts, top_s, top_u):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    s_items  = '\n'.join([f"- {a['title']}" for a in top_s]) or '(없음)'
    u_items  = '\n'.join([f"- {a['title']}" for a in top_u]) or '(없음)'
    recent   = '\n'.join([f"- [{a['published']}] {a['title']}" for a in recent_arts[:25]])
    tl_items = '\n'.join([f"- [{a['published']}] {a['title']}" for a in tl_arts[:120]]) or recent

    # 논지 + 구체적 요구사항
    r1 = client.messages.create(model='claude-haiku-4-5-20251001', max_tokens=1200,
        messages=[{'role':'user','content':f"""삼성전자 노사 갈등 기사 제목들입니다.

[삼성측 기사]
{s_items}
[노조측 기사]
{u_items}

삼성 측과 노조 측 각각의 주요 논지(2~3문장 전체 입장 요약)와
구체적 요구/제안 항목(3개)을 작성하세요.
반드시 아래 형식 그대로 8줄만 출력하세요:

삼성측논지: (2~3문장)
삼성측요구1: (핵심 입장/제안 1항목, 한 문장)
삼성측요구2: (핵심 입장/제안 2항목, 한 문장)
삼성측요구3: (핵심 입장/제안 3항목, 한 문장)
노조측논지: (2~3문장)
노조측요구1: (핵심 요구사항 1항목, 한 문장)
노조측요구2: (핵심 요구사항 2항목, 한 문장)
노조측요구3: (핵심 요구사항 3항목, 한 문장)"""}])
    raw1 = r1.content[0].text

    def _pick(key, _raw=raw1):
        m = re.search(rf'{re.escape(key)}\s*:\s*(.+?)(?=\n\S|\Z)', _raw, re.DOTALL)
        return m.group(1).strip().replace('\n', ' ') if m else ''

    s_sum     = _pick('삼성측논지')
    s_demands = [d for d in [_pick(f'삼성측요구{i}') for i in range(1, 4)] if d]
    u_sum     = _pick('노조측논지')
    u_demands = [d for d in [_pick(f'노조측요구{i}') for i in range(1, 4)] if d]

    # 팩트 + 주요사건 타임라인
    r2 = client.messages.create(model='claude-haiku-4-5-20251001', max_tokens=2000,
        messages=[{'role':'user','content':f"""삼성전자 노사 갈등 기사들입니다.

[최근 기사]
{recent}

[전체 기간 기사 (2026년 2월~)]
{tl_items}

아래 형식으로만 출력하세요. FACT 5개, TIMELINE은 2026년 2월부터 현재까지 주요 사건 날짜순으로 빠짐없이(최대 25개):
FACT: (중립 사실)
FACT: (중립 사실)
FACT: (중립 사실)
FACT: (중립 사실)
FACT: (중립 사실)
TIMELINE: YYYY-MM-DD | (사건 요약)
TIMELINE: YYYY-MM-DD | (사건 요약)
...(날짜 오름차순, 중복 없이 모두)"""}])
    facts, timeline = [], []
    for line in r2.content[0].text.splitlines():
        line = line.strip()
        if line.startswith('FACT:'):
            facts.append(line[5:].strip())
        elif line.startswith('TIMELINE:'):
            body = line[9:].strip()
            if '|' in body:
                d, ev = body.split('|', 1)
                timeline.append({'date': d.strip(), 'event': ev.strip()})

    return s_sum, s_demands, u_sum, u_demands, facts, timeline

# ── 추이 저장 ────────────────────────────────────────────────────
def save_trend(now_str, s_pct, u_pct):
    history = []
    if os.path.exists(TREND_FILE):
        try:
            with open(TREND_FILE, encoding='utf-8') as f:
                history = json.load(f)
        except: pass
    key     = now_str[:13]
    history = [h for h in history if h.get('time','')[:13] != key]
    history.append({'time': now_str, 'samsung_pct': s_pct, 'union_pct': u_pct})
    history = history[-200:]
    with open(TREND_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False)

# ── 역사 데이터 백필 ────────────────────────────────────────────
TREND_START = datetime(2026, 2, 13)

def backfill_trend():
    if os.path.exists(TREND_FILE):
        try:
            with open(TREND_FILE, encoding='utf-8') as f:
                history = json.load(f)
            if any(h.get('time','')[:10] <= '2026-02-20' for h in history):
                return
        except: pass

    print('  역사 추이 백필 중 (2026-02-13~)...')
    history_data = []
    week_start   = TREND_START
    now          = datetime.now()

    while week_start < now - timedelta(days=3):
        week_end   = week_start + timedelta(days=7)
        after_str  = week_start.strftime('%Y-%m-%d')
        before_str = week_end.strftime('%Y-%m-%d')
        feeds = [
            f'https://news.google.com/rss/search?q={_enc(f"삼성 노조 파업 after:{after_str} before:{before_str}")}&hl=ko&gl=KR&ceid=KR:ko',
            f'https://news.google.com/rss/search?q={_enc(f"삼성전자 노조 after:{after_str} before:{before_str}")}&hl=ko&gl=KR&ceid=KR:ko',
        ]
        s_scores, u_scores = [], []
        seen = set()
        for url in feeds:
            try:
                feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
                for e in feed.entries[:40]:
                    link = e.get('link','')
                    if link in seen: continue
                    seen.add(link)
                    try:    pub = datetime(*e.published_parsed[:6])
                    except: continue
                    if not (week_start <= pub < week_end): continue
                    title = strip_html(e.get('title',''))
                    full  = title + ' ' + strip_html(e.get('summary',''))
                    if not is_relevant(full): continue
                    s, u  = score(full)
                    if s == 0 and u == 0:
                        tl = title.lower()
                        if   any(k in tl for k in FALLBACK_S): s = 1
                        elif any(k in tl for k in FALLBACK_U): u = 1
                        else: continue
                    if   s > u: s_scores.append(s)
                    elif u > s: u_scores.append(u)
                    elif s > 0: s_scores.append(s); u_scores.append(u)
            except: pass

        total_s = sum(s_scores) + len(s_scores) * 3
        total_u = sum(u_scores) + len(u_scores) * 3
        total   = total_s + total_u
        if total > 0:
            s_pct = round(total_s / total * 100)
            history_data.append({'time': week_start.strftime('%Y-%m-%d 12:00:00'),
                                  'samsung_pct': s_pct, 'union_pct': 100 - s_pct})
            print(f'    {after_str}: 삼성{s_pct}% ({len(s_scores)+len(u_scores)}건)')
        week_start = week_end

    if history_data:
        existing = []
        if os.path.exists(TREND_FILE):
            try:
                with open(TREND_FILE, encoding='utf-8') as f:
                    existing = json.load(f)
            except: pass
        merged = history_data + existing
        merged.sort(key=lambda x: x['time'])
        seen_k, deduped = set(), []
        for h in merged:
            k = h['time'][:13]
            if k not in seen_k:
                seen_k.add(k); deduped.append(h)
        with open(TREND_FILE, 'w', encoding='utf-8') as f:
            json.dump(deduped, f, ensure_ascii=False)
        print(f'  백필 완료: {len(history_data)}개 포인트')

# ── HTML 생성 ─────────────────────────────────────────────────────
def build_html(data, trend_history):
    data_js  = json.dumps(data,          ensure_ascii=False)
    trend_js = json.dumps(trend_history, ensure_ascii=False)
    upd      = data['updated_at']

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>삼성 vs 노조 언론전 실시간 분석</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{min-height:100vh;background:#07070f;color:#e8e8e8;font-family:'Noto Sans KR','Segoe UI',sans-serif;overflow-x:hidden}}
.bg{{position:fixed;inset:0;pointer-events:none;z-index:0;background:radial-gradient(ellipse 60% 80% at 10% 50%,rgba(13,71,161,.15) 0%,transparent 70%),radial-gradient(ellipse 60% 80% at 90% 50%,rgba(183,28,28,.15) 0%,transparent 70%)}}
/* login */
.login-wrap{{position:fixed;inset:0;z-index:999;display:flex;align-items:center;justify-content:center;background:#07070f}}
.login-card{{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1);border-radius:16px;padding:44px 38px;width:340px;text-align:center;backdrop-filter:blur(20px)}}
.login-badge{{font-size:11px;letter-spacing:3px;color:#555;margin-bottom:10px}}
.login-title{{font-size:20px;font-weight:700;color:#fff;margin-bottom:4px}}
.login-sub{{font-size:11px;color:#555;letter-spacing:1px;margin-bottom:28px}}
.login-div{{width:36px;height:2px;background:linear-gradient(90deg,#1565c0,#c62828);margin:0 auto 28px}}
.login-input{{width:100%;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.13);border-radius:10px;padding:13px;font-size:22px;letter-spacing:8px;color:#fff;text-align:center;outline:none;margin-bottom:14px}}
.login-btn{{width:100%;padding:13px;border:none;border-radius:10px;background:linear-gradient(135deg,#1565c0,#c62828);color:#fff;font-size:14px;font-weight:600;cursor:pointer}}
.login-err{{margin-top:12px;color:#ef5350;font-size:12px;min-height:18px}}
/* main */
.main{{display:none}}
header{{position:relative;z-index:10;display:flex;align-items:center;justify-content:space-between;padding:12px 24px;background:rgba(0,0,0,.5);border-bottom:1px solid rgba(255,255,255,.07);backdrop-filter:blur(16px)}}
.site-badge{{font-size:10px;letter-spacing:2px;color:#555;text-transform:uppercase}}
.hdr-r{{display:flex;align-items:center;gap:10px}}
.upd-time{{font-size:11px;color:#444}}
.logout-btn{{padding:6px 12px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);border-radius:7px;color:#666;font-size:11px;cursor:pointer}}
.logout-btn:hover{{color:#fff}}
/* 메인 타이틀 */
.main-title-wrap{{position:relative;z-index:5;text-align:center;padding:40px 20px 16px}}
.main-title{{font-size:42px;font-weight:900;color:#fff;line-height:1.2;letter-spacing:-1px}}
.main-title .vs-word{{background:linear-gradient(90deg,#42a5f5,#ef5350);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.main-title-sub{{font-size:13px;color:#555;letter-spacing:2px;margin-top:10px}}
/* VS hero */
.vs-hero{{position:relative;z-index:5;display:flex;align-items:center;justify-content:center;padding:8px 20px 16px}}
.sl{{flex:1;text-align:center}}.sl .name{{font-size:22px;font-weight:900;display:block;margin-bottom:3px}}.sl .sub{{font-size:10px;color:#555;letter-spacing:1.5px}}
.sl.samsung .name{{color:#42a5f5}}.sl.union .name{{color:#ef5350}}
.vsc{{width:60px;text-align:center;flex-shrink:0}}
.vs-text{{font-size:28px;font-weight:900;background:linear-gradient(180deg,#fff,#555);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.vs-sub{{font-size:9px;color:#444;letter-spacing:2px;margin-top:2px}}
/* score bar */
.score-sec{{position:relative;z-index:5;padding:0 24px 18px}}
.bar-wrap{{position:relative;background:rgba(255,255,255,.05);border-radius:999px;height:40px;overflow:hidden;border:1px solid rgba(255,255,255,.07)}}
.bar-s{{position:absolute;left:0;top:0;bottom:0;background:linear-gradient(90deg,#0d47a1,#1976d2);border-radius:999px 0 0 999px;display:flex;align-items:center;padding-left:14px;transition:width 1.2s cubic-bezier(.22,1,.36,1)}}
.bar-u{{position:absolute;right:0;top:0;bottom:0;background:linear-gradient(270deg,#b71c1c,#e53935);border-radius:0 999px 999px 0;display:flex;align-items:center;justify-content:flex-end;padding-right:14px;transition:width 1.2s cubic-bezier(.22,1,.36,1)}}
.bar-pct{{font-size:15px;font-weight:800;color:rgba(255,255,255,.9)}}
.score-labels{{display:flex;justify-content:space-between;margin-top:7px;padding:0 2px}}
.sl-item{{font-size:10px;color:#505050}}.sl-item.as{{color:#42a5f5;font-weight:600}}.sl-item.au{{color:#ef5350;font-weight:600}}
.win-badge{{text-align:center;margin-top:5px;font-size:12px;color:#888}}
.win-badge .ws{{color:#42a5f5;font-weight:700}}.win-badge .wu{{color:#ef5350;font-weight:700}}
.score-note{{text-align:center;font-size:10px;color:#383838;margin-top:5px}}
/* facts + timeline (2-col) */
.ft-sec{{position:relative;z-index:5;display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:0 24px 18px}}
.panel{{background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.07);border-radius:11px;padding:16px}}
.panel-title{{font-size:10px;font-weight:700;letter-spacing:2px;color:#999;text-transform:uppercase;margin-bottom:12px;display:flex;align-items:center;gap:7px}}
.dot-y{{width:6px;height:6px;border-radius:50%;background:#ffd54f;box-shadow:0 0 5px #ffd54f;flex-shrink:0}}
.dot-g{{width:6px;height:6px;border-radius:50%;background:#b0bec5;box-shadow:0 0 5px #b0bec5;flex-shrink:0}}
.dot-r{{width:6px;height:6px;border-radius:50%;background:#ef5350;box-shadow:0 0 5px #ef5350;flex-shrink:0}}
.fact-item{{display:flex;gap:9px;padding:8px 0;border-bottom:1px solid rgba(255,255,255,.04)}}
.fact-item:last-child{{border-bottom:none}}
.fact-num{{font-size:10px;color:#ffd54f;font-weight:700;flex-shrink:0;width:16px}}
.fact-text{{font-size:11.5px;color:#ccc;line-height:1.65}}
.tl-item{{display:flex;gap:10px;padding:7px 0;border-bottom:1px solid rgba(255,255,255,.04)}}
.tl-item:last-child{{border-bottom:none}}
.tl-dot{{width:7px;height:7px;border-radius:50%;background:#546e7a;flex-shrink:0;margin-top:4px}}
.tl-dot-r{{width:7px;height:7px;border-radius:50%;background:#c62828;flex-shrink:0;margin-top:4px}}
.tl-date{{font-size:10px;color:#555;font-weight:600;white-space:nowrap;width:72px;flex-shrink:0;margin-top:2px}}
.tl-ev{{font-size:11.5px;color:#ccc;line-height:1.6}}
.scroll-panel{{max-height:480px;overflow-y:auto}}
/* summary (논지 + 요구사항) */
.sum-sec{{position:relative;z-index:5;display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:0 24px 14px}}
.sum-card{{border-radius:11px;padding:16px 18px}}
.sum-card.samsung{{background:linear-gradient(135deg,rgba(13,71,161,.18),rgba(13,71,161,.05));border:1px solid rgba(21,101,192,.3)}}
.sum-card.union{{background:linear-gradient(135deg,rgba(183,28,28,.18),rgba(183,28,28,.05));border:1px solid rgba(198,40,40,.3)}}
.sum-label{{font-size:9px;font-weight:700;letter-spacing:2px;margin-bottom:9px;text-transform:uppercase}}
.sum-card.samsung .sum-label{{color:#42a5f5}}.sum-card.union .sum-label{{color:#ef5350}}
.sum-text{{font-size:12px;line-height:1.8;color:#bbb;margin-bottom:13px;padding-bottom:12px;border-bottom:1px solid rgba(255,255,255,.07)}}
.demand-label{{font-size:9px;font-weight:700;letter-spacing:1.5px;color:#555;margin-bottom:8px;text-transform:uppercase}}
.demand-list{{list-style:none;padding:0;margin:0}}
.demand-item{{display:flex;gap:8px;padding:6px 0;font-size:11.5px;color:#b0b0b0;line-height:1.65;border-bottom:1px solid rgba(255,255,255,.04)}}
.demand-item:last-child{{border-bottom:none}}
.demand-bullet{{flex-shrink:0;margin-top:3px;width:5px;height:5px;border-radius:50%}}
.sum-card.samsung .demand-bullet{{background:#1976d2;box-shadow:0 0 4px #1976d2}}
.sum-card.union .demand-bullet{{background:#e53935;box-shadow:0 0 4px #e53935}}
/* article grid */
.grid{{position:relative;z-index:5;display:grid;grid-template-columns:1fr 1fr;padding:0 16px 24px}}
.col{{padding:0 12px}}
.col-hdr{{display:flex;align-items:center;gap:8px;margin-bottom:12px;padding-bottom:9px;border-bottom:1px solid rgba(255,255,255,.06)}}
.col-hdr .dot{{width:7px;height:7px;border-radius:50%;flex-shrink:0}}
.col.samsung .dot{{background:#1976d2;box-shadow:0 0 6px #1976d2}}.col.union .dot{{background:#e53935;box-shadow:0 0 6px #e53935}}
.col-title{{font-size:12.5px;font-weight:700}}
.col.samsung .col-title{{color:#42a5f5}}.col.union .col-title{{color:#ef5350}}
.col-cnt{{font-size:10px;padding:2px 7px;border-radius:20px;font-weight:700}}
.col.samsung .col-cnt{{background:rgba(21,101,192,.25);color:#64b5f6}}.col.union .col-cnt{{background:rgba(198,40,40,.25);color:#ef9a9a}}
.col-sub{{font-size:10px;color:#444;margin-left:auto}}
.art-card{{background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.06);border-radius:9px;padding:13px;margin-bottom:9px;position:relative;overflow:hidden;transition:all .2s}}
.art-card::before{{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;border-radius:3px 0 0 3px}}
.col.samsung .art-card::before{{background:linear-gradient(180deg,#1565c0,#0d47a1)}}.col.union .art-card::before{{background:linear-gradient(180deg,#c62828,#b71c1c)}}
.art-card:hover{{background:rgba(255,255,255,.05);transform:translateY(-1px)}}
.art-rank{{font-size:10px;font-weight:700;letter-spacing:1px;margin-bottom:6px}}
.col.samsung .art-rank{{color:#1976d2}}.col.union .art-rank{{color:#e53935}}
.art-title{{font-size:13px;font-weight:600;color:#e0e0e0;line-height:1.5;margin-bottom:6px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}
.art-title a{{color:inherit;text-decoration:none}}.art-title a:hover{{text-decoration:underline}}
.art-sum{{font-size:11px;color:#606060;line-height:1.6;margin-bottom:8px;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}}
.art-meta{{display:flex;font-size:10px;color:#484848;align-items:center}}
.art-meta .date{{margin-left:auto}}
.badge-jsn{{display:inline-block;font-size:9px;font-weight:700;letter-spacing:.5px;padding:1px 6px;border-radius:4px;background:rgba(198,40,40,.25);color:#ef9a9a;margin-right:5px}}
/* YouTube */
.sec-divider{{position:relative;z-index:5;padding:4px 24px 14px}}
.sec-divider-line{{border:none;border-top:1px solid rgba(255,255,255,.06);margin-bottom:14px}}
.sec-label{{font-size:10px;font-weight:700;letter-spacing:3px;color:#444;text-transform:uppercase;margin-bottom:12px;display:flex;align-items:center;gap:8px}}
.sec-label::after{{content:'';flex:1;height:1px;background:rgba(255,255,255,.06)}}
.yt-sec{{position:relative;z-index:5;display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:0 24px 18px}}
.yt-col{{background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.07);border-radius:11px;padding:16px}}
.yt-col-hdr{{font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;margin-bottom:12px;display:flex;align-items:center;gap:7px}}
.yt-col.samsung .yt-col-hdr{{color:#42a5f5}}.yt-col.union .yt-col-hdr{{color:#ef5350}}
.yt-cnt{{font-size:10px;padding:2px 7px;border-radius:20px;font-weight:700}}
.yt-col.samsung .yt-cnt{{background:rgba(21,101,192,.25);color:#64b5f6}}.yt-col.union .yt-cnt{{background:rgba(198,40,40,.25);color:#ef9a9a}}
.yt-card{{display:flex;gap:10px;padding:10px 0;border-bottom:1px solid rgba(255,255,255,.04)}}
.yt-card:last-child{{border-bottom:none}}
.yt-thumb{{width:96px;height:54px;border-radius:6px;object-fit:cover;flex-shrink:0;background:#111}}
.yt-info{{flex:1;min-width:0}}
.yt-title{{font-size:12px;font-weight:600;color:#e0e0e0;line-height:1.5;margin-bottom:4px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}
.yt-title a{{color:inherit;text-decoration:none}}.yt-title a:hover{{text-decoration:underline}}
.yt-meta{{font-size:10px;color:#555;display:flex;flex-wrap:wrap;gap:6px;align-items:center}}
.yt-views{{color:#ffd54f;font-weight:600}}
/* 언론사 랭킹 */
.media-sec{{position:relative;z-index:5;display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:0 24px 18px}}
.media-col{{background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.07);border-radius:11px;padding:16px}}
.media-hdr{{font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;margin-bottom:14px;display:flex;align-items:center;gap:7px}}
.media-col.samsung .media-hdr{{color:#42a5f5}}.media-col.union .media-hdr{{color:#ef5350}}
.media-row{{display:flex;align-items:center;gap:8px;padding:7px 0;border-bottom:1px solid rgba(255,255,255,.04)}}
.media-row:last-child{{border-bottom:none}}
.media-rank{{font-size:11px;font-weight:700;width:22px;flex-shrink:0;color:#505050}}
.media-rank.top3{{color:#ffd54f}}
.media-name{{font-size:12px;color:#ccc;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.media-bar-wrap{{width:70px;background:rgba(255,255,255,.05);border-radius:3px;height:5px;flex-shrink:0}}
.media-col.samsung .media-bar{{background:#1976d2;height:5px;border-radius:3px}}
.media-col.union .media-bar{{background:#e53935;height:5px;border-radius:3px}}
.media-cnt{{font-size:11px;font-weight:600;width:28px;text-align:right;flex-shrink:0}}
.media-col.samsung .media-cnt{{color:#64b5f6}}.media-col.union .media-cnt{{color:#ef9a9a}}
/* trend */
.trend-sec{{position:relative;z-index:5;padding:0 24px 36px}}
.trend-panel{{background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.07);border-radius:12px;padding:20px 24px}}
.trend-title{{font-size:10px;font-weight:700;letter-spacing:2px;color:#888;text-transform:uppercase;margin-bottom:16px;display:flex;align-items:center;justify-content:space-between}}
.trend-legend{{display:flex;gap:16px}}
.tl-i{{display:flex;align-items:center;gap:5px;font-size:10px;color:#555}}
.tl-dot2{{width:8px;height:8px;border-radius:50%}}
.chart-wrap{{position:relative;height:180px}}
/* sched */
.sched{{position:relative;z-index:5;display:flex;align-items:center;justify-content:center;gap:5px;padding:10px;font-size:10px;color:#383838;border-top:1px solid rgba(255,255,255,.04)}}
.sched span{{color:#505050;font-weight:600}}
/* responsive */
@media(max-width:900px){{
  .ft-sec{{grid-template-columns:1fr 1fr}}
}}
@media(max-width:768px){{
  .ft-sec,.sum-sec,.yt-sec,.media-sec,.grid{{grid-template-columns:1fr}}
  header{{flex-direction:column;align-items:flex-start;gap:8px}}
  .hdr-r{{flex-wrap:wrap}}
  .main-title{{font-size:26px}}
  .bar-pct{{font-size:13px}}
}}
</style>
</head>
<body>
<div class="bg"></div>

<!-- 로그인 -->
<div class="login-wrap" id="loginWrap">
  <div class="login-card">
    <div class="login-badge">Samsung Media Intelligence</div>
    <div class="login-title">삼성 vs 노조</div>
    <div class="login-sub">언론전 실시간 분석</div>
    <div class="login-div"></div>
    <input class="login-input" id="pwInput" type="password" placeholder="비밀번호" maxlength="10" autocomplete="off">
    <button class="login-btn" onclick="doLogin()">입장하기</button>
    <div class="login-err" id="loginErr"></div>
  </div>
</div>

<!-- 메인 -->
<div class="main" id="mainWrap">
<header>
  <div class="site-badge">Samsung Media Intelligence</div>
  <div class="hdr-r">
    <div class="upd-time">최종 업데이트: {upd}</div>
    <span class="logout-btn" onclick="doLogout()">로그아웃</span>
  </div>
</header>

<!-- 메인 타이틀 -->
<div class="main-title-wrap">
  <div class="main-title">삼성 <span class="vs-word">vs</span> 노조 — 언론전 실시간 분석</div>
  <div class="main-title-sub">실시간 분석 · 뉴스 + 유튜브 통합</div>
</div>

<!-- VS hero -->
<div class="vs-hero">
  <div class="sl samsung"><span class="name">삼성</span><span class="sub">SAMSUNG CORP.</span></div>
  <div class="vsc"><div class="vs-text">VS</div><div class="vs-sub">언론전</div></div>
  <div class="sl union"><span class="name">노조</span><span class="sub">LABOR UNION</span></div>
</div>

<!-- 점수바 (뉴스+유튜브 통합) -->
<div class="score-sec">
  <div class="bar-wrap">
    <div class="bar-s" id="barS" style="width:50%"><span class="bar-pct" id="pctS">-</span></div>
    <div class="bar-u" id="barU" style="width:50%"><span class="bar-pct" id="pctU">-</span></div>
  </div>
  <div class="score-labels">
    <div class="sl-item" id="lblS">삼성 우세</div>
    <div class="sl-item" id="lblC">빈도+강도 기준</div>
    <div class="sl-item" id="lblU">노조 우세</div>
  </div>
  <div class="win-badge" id="winB"></div>
  <div class="score-note">뉴스 70% + 유튜브 30% 통합 점수</div>
</div>

<!-- 팩트 + 타임라인 (2열) -->
<div class="ft-sec">
  <div class="panel">
    <div class="panel-title"><span class="dot-y"></span>실시간 팩트 현황<span style="color:#444;font-size:9px;margin-left:auto">중립·사실 기반</span></div>
    <div id="factsList"></div>
  </div>
  <div class="panel">
    <div class="panel-title"><span class="dot-g"></span>주요 사건 타임라인<span style="color:#444;font-size:9px;margin-left:auto">2026.02~</span></div>
    <div id="timelineList" class="scroll-panel"></div>
  </div>
</div>

<!-- 논지 + 구체적 요구사항 -->
<div class="sec-divider"><div class="sec-label">주요 논지 및 구체적 요구사항</div></div>
<div class="sum-sec">
  <div class="sum-card samsung">
    <div class="sum-label">삼성 측 주요 논지</div>
    <div class="sum-text" id="sumS"></div>
    <div class="demand-label">구체적 입장 / 제안</div>
    <ul class="demand-list" id="demandS"></ul>
  </div>
  <div class="sum-card union">
    <div class="sum-label">노조 측 주요 논지</div>
    <div class="sum-text" id="sumU"></div>
    <div class="demand-label">구체적 요구사항</div>
    <ul class="demand-list" id="demandU"></ul>
  </div>
</div>

<!-- 뉴스 기사 -->
<div class="grid">
  <div class="col samsung">
    <div class="col-hdr"><div class="dot"></div><div class="col-title">실시간 삼성 측 우세 기사</div><span class="col-cnt" id="cntS">-</span><div class="col-sub">삼성 옹호 / 노조 비판</div></div>
    <div id="artS"></div>
  </div>
  <div class="col union">
    <div class="col-hdr"><div class="dot"></div><div class="col-title">실시간 노조 측 우세 기사</div><span class="col-cnt" id="cntU">-</span><div class="col-sub">노조 옹호 / 삼성 비판</div></div>
    <div id="artU"></div>
  </div>
</div>

<!-- 유튜브 섹션 -->
<div class="sec-divider"><div class="sec-label">유튜브 언론전</div></div>
<div class="yt-sec">
  <div class="yt-col samsung">
    <div class="yt-col-hdr"><span class="dot-y" style="background:#42a5f5;box-shadow:0 0 5px #42a5f5"></span>삼성 측 우세 유튜브 TOP 5<span class="yt-cnt" id="cntYtS" style="margin-left:auto">-</span></div>
    <div id="ytS"></div>
  </div>
  <div class="yt-col union">
    <div class="yt-col-hdr"><span class="dot-y" style="background:#ef5350;box-shadow:0 0 5px #ef5350"></span>노조 측 우세 유튜브 TOP 5<span class="yt-cnt" id="cntYtU" style="margin-left:auto">-</span></div>
    <div id="ytU"></div>
  </div>
</div>

<!-- 언론사 편향도 랭킹 -->
<div class="sec-divider"><div class="sec-label">언론사 편향도 TOP 10 <span style="font-size:9px;color:#444;letter-spacing:0;font-weight:400">최근 100일 기준</span></div></div>
<div class="media-sec">
  <div class="media-col samsung">
    <div class="media-hdr"><span class="dot-y" style="background:#42a5f5;box-shadow:0 0 5px #42a5f5"></span>삼성 우호 언론사</div>
    <div id="mediaS"></div>
  </div>
  <div class="media-col union">
    <div class="media-hdr"><span class="dot-y" style="background:#ef5350;box-shadow:0 0 5px #ef5350"></span>노조 우호 언론사</div>
    <div id="mediaU"></div>
  </div>
</div>

<!-- 일자별 추이 -->
<div class="sec-divider"><div class="sec-label">일자별 언론전 추이</div></div>
<div class="trend-sec">
  <div class="trend-panel">
    <div class="trend-title">뉴스 + 유튜브 통합 추이 (2026.02~)
      <div class="trend-legend">
        <div class="tl-i"><div class="tl-dot2" style="background:#1976d2"></div>삼성</div>
        <div class="tl-i"><div class="tl-dot2" style="background:#e53935"></div>노조</div>
      </div>
    </div>
    <div class="chart-wrap"><canvas id="trendChart"></canvas></div>
  </div>
</div>

<div class="sched">자동 업데이트: <span>08:00</span>·<span>12:00</span>·<span>16:00</span> KST &nbsp;|&nbsp; 범위: 전일 00:00~현재 국내외 삼성 노조 기사+유튜브</div>
</div>

<script>
const DATA  = {data_js};
const TREND = {trend_js};

function doLogin(){{
  const pw = document.getElementById('pwInput').value;
  if(pw==='321'){{
    sessionStorage.setItem('auth','1');
    document.getElementById('loginWrap').style.display='none';
    document.getElementById('mainWrap').style.display='block';
    render();
  }} else {{
    document.getElementById('loginErr').textContent='비밀번호가 틀렸습니다.';
  }}
}}
function doLogout(){{
  sessionStorage.removeItem('auth');
  location.reload();
}}
document.getElementById('pwInput').addEventListener('keydown',e=>{{if(e.key==='Enter')doLogin();}});

function fmtViews(n){{
  if(!n) return '';
  n = parseInt(n);
  if(n>=10000) return (n/10000).toFixed(1)+'만회';
  if(n>=1000)  return (n/1000).toFixed(1)+'천회';
  return n+'회';
}}

function render(){{
  const d = DATA;

  // 점수바 (통합)
  const sp = d.combined_s_pct || d.samsung_pct;
  const up = d.combined_u_pct || d.union_pct;
  document.getElementById('barS').style.width = sp+'%';
  document.getElementById('barU').style.width = up+'%';
  document.getElementById('pctS').textContent = sp+'%';
  document.getElementById('pctU').textContent = up+'%';
  document.getElementById('lblS').className='sl-item';
  document.getElementById('lblU').className='sl-item';
  if(sp>up){{
    document.getElementById('winB').innerHTML=`현재 <span class="ws">삼성 측</span> 언론 우세 (${{sp}} : ${{up}})`;
    document.getElementById('lblS').classList.add('as');
  }} else if(up>sp){{
    document.getElementById('winB').innerHTML=`현재 <span class="wu">노조 측</span> 언론 우세 (${{sp}} : ${{up}})`;
    document.getElementById('lblU').classList.add('au');
  }} else document.getElementById('winB').textContent='50 : 50 균형';

  // 논지 + 구체적 요구사항
  document.getElementById('sumS').textContent = d.samsung_summary || '-';
  document.getElementById('sumU').textContent = d.union_summary   || '-';
  function demandHTML(items) {{
    if (!items || !items.length) return '';
    return items.map(t => `<li class="demand-item"><span class="demand-bullet"></span>${{t}}</li>`).join('');
  }}
  document.getElementById('demandS').innerHTML = demandHTML(d.samsung_demands);
  document.getElementById('demandU').innerHTML = demandHTML(d.union_demands);

  // 기사 카운트
  document.getElementById('cntS').textContent = '총 '+d.samsung_total+'건';
  document.getElementById('cntU').textContent = '총 '+d.union_total+'건';

  // 팩트
  document.getElementById('factsList').innerHTML=(d.facts||[]).map((f,i)=>
    `<div class="fact-item"><span class="fact-num">${{i+1}}</span><span class="fact-text">${{f}}</span></div>`).join('');

  // 주요 타임라인
  document.getElementById('timelineList').innerHTML=(d.timeline||[]).map(t=>
    `<div class="tl-item"><div class="tl-dot"></div><div class="tl-date">${{t.date}}</div><div class="tl-ev">${{t.event}}</div></div>`).join('');

  // 뉴스 기사
  function artHTML(arts){{
    if(!arts||!arts.length) return '<div style="color:#3a3a3a;padding:24px;text-align:center;font-size:12px">해당 기사 없음</div>';
    return arts.map((a,i)=>{{
      const isJsn = a.source==='전삼노';
      const badge = isJsn ? '<span class="badge-jsn">전삼노 공식</span>' : '';
      return `<div class="art-card">
      <div class="art-rank">#${{i+1}} 중요도순</div>
      <div class="art-title"><a href="${{a.link}}" target="_blank" rel="noopener">${{a.title}}</a></div>
      ${{!isJsn && a.summary ? `<div class="art-sum">${{a.summary}}</div>` : ''}}
      <div class="art-meta">${{badge}}<span>${{isJsn?'':a.source||''}}</span><span class="date">${{a.published||''}}</span></div>
    </div>`;
    }}).join('');
  }}
  document.getElementById('artS').innerHTML = artHTML(d.samsung);
  document.getElementById('artU').innerHTML = artHTML(d.union);

  // 유튜브 카운트
  document.getElementById('cntYtS').textContent = '총 '+(d.yt_s_cnt||0)+'건';
  document.getElementById('cntYtU').textContent = '총 '+(d.yt_u_cnt||0)+'건';

  // 유튜브 카드
  function ytHTML(vids){{
    if(!vids||!vids.length) return '<div style="color:#3a3a3a;padding:20px;text-align:center;font-size:11px">유튜브 데이터 없음</div>';
    return vids.map(v=>{{
      const views = fmtViews(v.view_count);
      return `<div class="yt-card">
        <img class="yt-thumb" src="${{v.thumbnail||''}}" alt="" loading="lazy" onerror="this.style.display='none'">
        <div class="yt-info">
          <div class="yt-title"><a href="${{v.url}}" target="_blank" rel="noopener">${{v.title}}</a></div>
          <div class="yt-meta">
            <span>${{v.channel||''}}</span>
            ${{views?`<span class="yt-views">${{views}}</span>`:''}}
            <span style="margin-left:auto">${{v.upload_date||''}}</span>
          </div>
        </div>
      </div>`;
    }}).join('');
  }}
  document.getElementById('ytS').innerHTML = ytHTML(d.yt_samsung);
  document.getElementById('ytU').innerHTML = ytHTML(d.yt_union);

  // 언론사 랭킹
  function mediaHTML(media){{
    if(!media||!media.length) return '<div style="color:#3a3a3a;padding:12px;text-align:center;font-size:11px">데이터 없음</div>';
    const max = media[0][1];
    return media.map(([name,cnt],i)=>
      `<div class="media-row">
        <span class="media-rank ${{i<3?'top3':''}}">#${{i+1}}</span>
        <span class="media-name">${{name}}</span>
        <div class="media-bar-wrap"><div class="media-bar" style="width:${{Math.round(cnt/max*100)}}%"></div></div>
        <span class="media-cnt">${{cnt}}</span>
      </div>`).join('');
  }}
  document.getElementById('mediaS').innerHTML = mediaHTML(d.s_media);
  document.getElementById('mediaU').innerHTML = mediaHTML(d.u_media);

  // 추이 차트
  if(TREND&&TREND.length>1){{
    const labels = TREND.map(h=>TREND.length>30 ? h.time.slice(5,10) : h.time.slice(5,16));
    new Chart(document.getElementById('trendChart').getContext('2d'),{{
      type:'line',
      data:{{labels,datasets:[
        {{label:'삼성',data:TREND.map(h=>h.samsung_pct),borderColor:'#1976d2',backgroundColor:'rgba(25,118,210,.12)',fill:true,tension:0.4,pointRadius:3,borderWidth:2}},
        {{label:'노조',data:TREND.map(h=>h.union_pct),  borderColor:'#e53935',backgroundColor:'rgba(229,57,53,.10)',fill:true,tension:0.4,pointRadius:3,borderWidth:2}}
      ]}},
      options:{{responsive:true,maintainAspectRatio:false,
        scales:{{
          x:{{ticks:{{color:'#555',font:{{size:9}},maxRotation:30}},grid:{{color:'rgba(255,255,255,.04)'}}}},
          y:{{min:0,max:100,ticks:{{color:'#555',font:{{size:9}},callback:v=>v+'%'}},grid:{{color:'rgba(255,255,255,.05)'}}}}
        }},
        plugins:{{legend:{{display:false}},tooltip:{{backgroundColor:'rgba(10,10,20,.9)',callbacks:{{label:ctx=>` ${{ctx.dataset.label}}: ${{ctx.parsed.y}}%`}}}}}}
      }}
    }});
  }} else {{
    document.getElementById('trendChart').parentElement.innerHTML='<div style="color:#333;text-align:center;padding:60px 0;font-size:12px">업데이트가 쌓이면 추이 그래프가 표시됩니다</div>';
  }}
}}

if(sessionStorage.getItem('auth')==='1'){{
  document.getElementById('loginWrap').style.display='none';
  document.getElementById('mainWrap').style.display='block';
  render();
}}
</script>
</body>
</html>"""

# ── 메인 ─────────────────────────────────────────────────────────
def main():
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{now_str}] 시작')

    print('뉴스 수집 중...')
    arts    = fetch_articles()
    tl_arts = fetch_timeline_articles()
    print(f'  최근 {len(arts)}건 / 타임라인용 {len(tl_arts)}건')

    print('유튜브 수집 중...')
    yt_videos = fetch_youtube_videos()

    print('분류 중...')
    top_s, top_u, s_pct, u_pct, s_cnt, u_cnt = classify(arts)
    print(f'  뉴스 삼성측 {s_cnt}건 / 노조측 {u_cnt}건 | {s_pct}:{u_pct}')

    print('전삼노 홈페이지 수집 중...')
    jsn_posts = fetch_jeonsamno()
    jsn_arts  = [{'title': p['title'], 'link': p['link'], 'summary': '전삼노 공식 홍보물',
                  'published': p['date'], 'source': '전삼노'} for p in jsn_posts[:4]]
    top_u     = jsn_arts + top_u   # 전삼노 글을 노조측 기사 상단에 배치
    u_cnt    += len(jsn_arts)
    print(f'  전삼노 {len(jsn_arts)}건 추가 → 노조측 총 {u_cnt}건')

    print('100일 언론사 편향 분석 중...')
    arts_100d = fetch_articles_100days()
    s_media, u_media = compute_media_bias(arts_100d)
    print(f'  100일 기사 {len(arts_100d)}건 → 삼성우호 {len(s_media)}개 언론사 / 노조우호 {len(u_media)}개 언론사')

    top_s_yt, top_u_yt, yt_s_cnt, yt_u_cnt, yt_s_pct, yt_u_pct = classify_youtube(yt_videos)
    print(f'  유튜브 삼성측 {yt_s_cnt}건 / 노조측 {yt_u_cnt}건 | {yt_s_pct}:{yt_u_pct}')

    # 뉴스 70% + 유튜브 30% 통합 점수
    combined_s = round(s_pct * 0.7 + yt_s_pct * 0.3)
    combined_u = 100 - combined_s

    print('역사 추이 백필 확인 중...')
    backfill_trend()

    print('Claude 요약 생성 중...')
    s_sum, s_demands, u_sum, u_demands, facts, timeline = ai_generate(arts, tl_arts, top_s, top_u)

    data = {
        'updated_at':      now_str,
        'samsung':         top_s,
        'union':           top_u,
        'samsung_pct':     s_pct,
        'union_pct':       u_pct,
        'combined_s_pct':  combined_s,
        'combined_u_pct':  combined_u,
        'total_fetched':   len(arts),
        'samsung_total':   s_cnt,
        'union_total':     u_cnt,
        'samsung_summary': s_sum,
        'samsung_demands': s_demands,
        'union_summary':   u_sum,
        'union_demands':   u_demands,
        'facts':           facts,
        'timeline':        timeline,
        'yt_samsung':      top_s_yt,
        'yt_union':        top_u_yt,
        'yt_s_cnt':        yt_s_cnt,
        'yt_u_cnt':        yt_u_cnt,
        'yt_s_pct':        yt_s_pct,
        'yt_u_pct':        yt_u_pct,
        's_media':         s_media,
        'u_media':         u_media,
    }

    save_trend(now_str, combined_s, combined_u)
    trend_history = []
    if os.path.exists(TREND_FILE):
        with open(TREND_FILE, encoding='utf-8') as f:
            trend_history = json.load(f)

    print('HTML 생성 중...')
    html = build_html(data, trend_history)
    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'완료 → {OUT_FILE}')

if __name__ == '__main__':
    main()
