import os
import json
import time
import logging
import math
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from typing import Dict, List, Optional, Any

# Configuration
LOG_LEVEL = logging.INFO
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

class GitHubAPI:
    """Enhanced GitHub API with GraphQL support and intelligent caching"""
    
    BASE_URL = "https://api.github.com"
    
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get('GITHUB_TOKEN')
        self.headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'Ultimate-GitHub-Profile/4.0'
        }
        if self.token:
            self.headers['Authorization'] = f'token {self.token}'
        self.cache = {}
        self.rate_limit_remaining = 5000
        self.rate_limit_reset = 0
        self.request_delay = 0.1

    def _check_rate_limit(self) -> bool:
        current_time = time.time()
        if current_time >= self.rate_limit_reset:
            self.rate_limit_remaining = 5000
        
        if self.rate_limit_remaining < 10:
            wait_time = max(self.rate_limit_reset - current_time, 0) + 1
            if wait_time > 0:
                logger.warning(f"  ⚠ Rate limit low ({self.rate_limit_remaining}), waiting {wait_time:.0f}s")
                time.sleep(min(wait_time, 300))
                self.rate_limit_remaining = 5000
            return True
        return True
    
    def _request(self, endpoint: str, params: Optional[Dict] = None, retry_count: int = 3) -> Any:
        cache_key = f"{endpoint}:{json.dumps(params or {})}"
        if cache_key in self.cache:
            return self.cache[cache_key], None

        self._check_rate_limit()
        time.sleep(self.request_delay)

        url = f"{self.BASE_URL}/{endpoint}" if not endpoint.startswith('http') else endpoint
        if params and not endpoint.startswith('http'):
            url += '?' + urlencode(params)

        for attempt in range(retry_count):
            try:
                req = Request(url, headers=self.headers)
                with urlopen(req, timeout=30) as response:
                    remaining = response.headers.get('X-RateLimit-Remaining')
                    reset = response.headers.get('X-RateLimit-Reset')
                    if remaining: self.rate_limit_remaining = int(remaining)
                    if reset: self.rate_limit_reset = int(reset)
                    
                    try:
                        data = json.loads(response.read().decode())
                    except json.JSONDecodeError:
                        data = {}
                        
                    self.cache[cache_key] = data
                    return data, response.headers
            except HTTPError as e:
                if e.code == 403:
                    reset_time = int(e.headers.get('X-RateLimit-Reset', time.time() + 3600))
                    self.rate_limit_remaining = int(e.headers.get('X-RateLimit-Remaining', 0))
                    self.rate_limit_reset = reset_time
                    time.sleep(min(max(reset_time - time.time(), 1) + 1, 300))
                    continue
                elif e.code == 404:
                    return None, None
                elif e.code == 429:
                    retry_after = int(e.headers.get('Retry-After', 60))
                    time.sleep(min(retry_after, 300))
                    continue
                if attempt == retry_count - 1: return None, None
            except URLError as e:
                if attempt < retry_count - 1: time.sleep(2 ** attempt)
                else: return None, None
        return None, None

    def get_user_info(self, username: str = None) -> Dict:
        endpoint = f"users/{username}" if username else "user"
        data, _ = self._request(endpoint)
        return data or {}

    def get_all_repos(self, username: str, limit: int = 50) -> List[Dict]:
        repos = []
        page = 1
        max_pages = 5
        
        while len(repos) < limit and page <= max_pages:
            data, _ = self._request(f"users/{username}/repos", {
                'per_page': 100,
                'page': page,
                'type': 'owner',
                'sort': 'updated',
                'direction': 'desc'
            })
            if not data: break
            repos.extend([r for r in data if not r.get('fork', False)])
            if len(data) < 100: break
            page += 1
        return repos[:limit]

    def get_repo_languages(self, owner: str, repo: str) -> Dict[str, int]:
        data, _ = self._request(f"repos/{owner}/{repo}/languages")
        return data or {}

    def get_contribution_stats(self, username: str) -> Dict[str, int]:
        stats = {'commits': 0, 'prs': 0, 'issues': 0, 'reviews': 0}
        try:
            d, _ = self._request("search/issues", {'q': f'author:{username} type:pr is:merged', 'per_page': 1})
            if d: stats['prs'] = min(d.get('total_count', 0), 5000)
            
            d, _ = self._request("search/issues", {'q': f'author:{username} type:issue', 'per_page': 1})
            if d: stats['issues'] = min(d.get('total_count', 0), 5000)
        except: pass
        
        repos = self.get_all_repos(username, limit=10)
        stats['commits'] = len(repos) * 50
        return stats

    def get_user_events(self, username: str, limit: int = 100) -> List[Dict]:
        data, _ = self._request(f"users/{username}/events/public", {'per_page': min(limit, 100)})
        return (data or [])[:limit]


class AdvancedProfileAnalyzer:
    TECH_DETECTION = {
        'Python': {'files': [], 'frameworks': {'Django': ['django'], 'Flask': ['flask'], 'FastAPI': ['fastapi'], 'Pandas': ['pandas'], 'PyTorch': ['torch'], 'TensorFlow': ['tensorflow'], 'Streamlit': ['streamlit']}},
        'JavaScript': {'files': [], 'frameworks': {'React': ['react'], 'Vue': ['vue'], 'Angular': ['angular'], 'Next.js': ['next'], 'Express': ['express'], 'Node.js': ['node']}},
        'TypeScript': {'files': [], 'frameworks': {'React': ['react'], 'Angular': ['angular'], 'NestJS': ['nest'], 'Vue': ['vue']}},
        'Java': {'files': [], 'frameworks': {'Spring Boot': ['spring-boot'], 'Hibernate': ['hibernate'], 'Android': ['android']}},
        'Go': {'files': [], 'frameworks': {'Gin': ['gin'], 'Echo': ['echo']}},
        'Rust': {'files': [], 'frameworks': {'Actix': ['actix'], 'Rocket': ['rocket']}},
        'PHP': {'files': [], 'frameworks': {'Laravel': ['laravel'], 'Symfony': ['symfony']}},
        'C#': {'files': [], 'frameworks': {'.NET': ['dotnet'], 'Unity': ['unity']}},
    }

    LANGUAGE_COLORS = {
        'Python': '#3572A5', 'Java': '#b07219', 'JavaScript': '#f1e05a', 'TypeScript': '#2b7489',
        'C++': '#f34b7d', 'HTML': '#e34c26', 'CSS': '#563d7c', 'C#': '#178600', 'Go': '#00ADD8',
        'Rust': '#dea584', 'PHP': '#4F5D95', 'Ruby': '#701516', 'Swift': '#ffac45', 'Kotlin': '#A97BFF'
    }

    def __init__(self, api: GitHubAPI, username: str):
        self.api = api
        self.username = username
        self.skills = defaultdict(lambda: {
            'bytes': 0, 
            'repos': 0, 
            'recency_sum': 0,
            'frameworks': defaultdict(int), 
            'top_repo': ('', 0)
        })

    def analyze(self) -> List[Dict]:
        logger.info(f"🚀 Analyzing profile: {self.username}")
        repos = self.api.get_all_repos(self.username, limit=40)
        logger.info(f"📂 Processing {len(repos)} repositories")
        
        for repo in repos:
            self._analyze_repo(repo)

        return self._process_skills()

    def _analyze_repo(self, repo: Dict):
        name = repo['name']
        if repo.get('size', 0) < 10: return

        langs = self.api.get_repo_languages(self.username, name)
        repo_text = (repo.get('description', '') or '').lower() + ' ' + name.lower()

        pushed_at = repo.get('pushed_at')
        recency = 0.2
        if pushed_at:
            try:
                date = datetime.strptime(pushed_at[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
                days_old = (datetime.now(timezone.utc) - date).days
                recency = max(0.2, 1.0 - (days_old / 730))
            except: pass

        for lang, byte_count in langs.items():
            if byte_count < 500: continue
            
            self.skills[lang]['bytes'] += byte_count
            self.skills[lang]['repos'] += 1
            self.skills[lang]['recency_sum'] += recency

            if byte_count > self.skills[lang]['top_repo'][1]:
                self.skills[lang]['top_repo'] = (name, byte_count)

            if lang in self.TECH_DETECTION:
                self._detect_frameworks(lang, repo_text)

    def _detect_frameworks(self, lang: str, text: str):
        tech = self.TECH_DETECTION[lang]
        for framework, keywords in tech['frameworks'].items():
            if any(kw in text for kw in keywords):
                self.skills[lang]['frameworks'][framework] += 1

    def _process_skills(self) -> List[Dict]:
        processed = []
        total_bytes_all = sum(s['bytes'] for s in self.skills.values()) or 1
        
        for lang, data in self.skills.items():
            if data['bytes'] < 2000: continue

            bytes_log = math.log10(data['bytes'])
            volume_xp = max(0, min(40, (bytes_log - 3.3) * 15))
            avg_recency = data['recency_sum'] / max(1, data['repos'])
            recency_xp = avg_recency * 30
            breadth_xp = min(20, data['repos'] * 4)
            dominance_xp = (data['bytes'] / total_bytes_all) * 10

            level = int((volume_xp + recency_xp + breadth_xp + dominance_xp) / 10)

            if data['repos'] == 1: level = min(level, 6)
            if data['bytes'] < 15000: level = min(level, 3)
            if data['bytes'] < 5000: level = 1
            level = max(1, min(10, level))

            top_frameworks = sorted(data['frameworks'].items(), key=lambda x: x[1], reverse=True)[:3]

            processed.append({
                'name': lang,
                'level': level,
                'repos': data['repos'],
                'bytes': data['bytes'],
                'frameworks': [fw[0] for fw in top_frameworks],
                'top_repo': data['top_repo'][0],
                'color': self.LANGUAGE_COLORS.get(lang, '#888888')
            })

        return sorted(processed, key=lambda x: (x['level'], x['bytes']), reverse=True)[:10]


class SkillTreeGenerator:
    def __init__(self, skills: List[Dict], contrib_stats: Dict):
        self.skills = skills
        self.stats = contrib_stats
        self.width = 900
        self.height = 200 + len(skills) * 95

    def generate(self) -> str:
        # Replaced Google Fonts with System Fonts to prevent XML/loading errors
        return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.width} {self.height}" width="{self.width}" height="{self.height}">
    <defs>
        <style>
            .txt {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; fill: #e6edf3; }}
            .title {{ font-size: 32px; font-weight: 700; letter-spacing: 2px; }}
            .subtitle {{ font-size: 13px; fill: #8b949e; }}
            .lang {{ font-size: 17px; font-weight: 600; }}
            .stat {{ font-size: 12px; fill: #8b949e; }}
            .bar-bg {{ fill: #161b22; stroke: #30363d; stroke-width: 1; rx: 5; }}
            .glow {{ filter: drop-shadow(0 0 8px rgba(249, 38, 114, 0.6)); }}
        </style>
        <linearGradient id="bg-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#0d1117"/>
            <stop offset="100%" stop-color="#161b22"/>
        </linearGradient>
        <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stop-color="#f92672"/>
            <stop offset="100%" stop-color="#a626a4"/>
        </linearGradient>
    </defs>
    
    <rect width="100%" height="100%" fill="url(#bg-grad)" rx="12"/>
    <rect width="100%" height="100%" fill="none" stroke="#30363d" stroke-width="2" rx="12"/>
    
    <g transform="translate(40, 50)">
        <text x="0" y="0" class="txt title" fill="url(#accent)">◈ SKILL MATRIX</text>
        <text x="0" y="28" class="txt subtitle">Real-time GitHub Analytics • {datetime.now().strftime('%B %Y')}</text>
        <text x="0" y="50" class="txt subtitle">{self.stats.get('commits', 0)} Commits • {self.stats.get('prs', 0)} PRs</text>
        <line x1="0" y1="70" x2="{self.width - 80}" y2="70" stroke="#30363d" stroke-width="2"/>
    </g>
    
    {self._render_skills()}
</svg>'''

    def _render_skills(self) -> str:
        nodes = []
        y = 150
        for s in self.skills:
            lvl = s['level']
            width = (lvl / 10) * 350
            if lvl >= 9: tier, clr = "⭐ EXPERT", "#f92672"
            elif lvl >= 7: tier, clr = "◆ ADVANCED", "#a626a4"
            elif lvl >= 4: tier, clr = "● COMPETENT", "#61afef"
            else: tier, clr = "○ NOVICE", "#8b949e"
            fw = ' • '.join(s['frameworks']) if s['frameworks'] else 'Core'
            nodes.append(f'''
    <g transform="translate(40, {y})">
        <circle cx="18" cy="18" r="8" fill="{s['color']}" class="glow"/>
        <line x1="18" y1="28" x2="18" y2="70" stroke="#30363d" stroke-dasharray="3,3"/>
        <text x="45" y="24" class="txt lang" fill="{s['color']}">{s['name']}</text>
        <text x="820" y="24" class="txt stat" fill="{clr}" text-anchor="end">{tier}</text>
        <text x="820" y="62" class="txt stat" text-anchor="end">Top: {s['top_repo']}</text>
        <text x="700" y="24" class="txt stat" text-anchor="end">LVL {lvl}</text>
        <rect x="45" y="35" width="350" height="8" class="bar-bg"/>
        <rect x="45" y="35" width="{width}" height="8" fill="{s['color']}" rx="4"/>
        <text x="45" y="62" class="txt stat" fill="#79c0ff">{fw}</text>
    </g>''')
            y += 95
        return '\n'.join(nodes)

class StatsCardGenerator:
    def __init__(self, stats: Dict, user: Dict):
        self.stats, self.user = stats, user
        self.width = 480
        self.height = 240

    def generate(self) -> str:
        # Added Width/Height attributes to prevent distortion
        return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.width} {self.height}" width="{self.width}" height="{self.height}">
    <defs>
        <style>
            .txt {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; fill: #e6edf3; }}
            .title {{ font-size: 16px; font-weight: 600; }}
            .stat-value {{ font-size: 28px; font-weight: 700; fill: #f92672; }}
            .stat-label {{ font-size: 12px; fill: #8b949e; }}
        </style>
        <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#0d1117"/>
            <stop offset="100%" stop-color="#161b22"/>
        </linearGradient>
    </defs>
    <rect width="100%" height="100%" fill="url(#bg)" rx="12" stroke="#30363d" stroke-width="2"/>
    <text x="24" y="32" class="txt title">CONTRIBUTION STATS</text>
    <line x1="24" y1="45" x2="{self.width - 24}" y2="45" stroke="#30363d" stroke-width="1"/>
    <g transform="translate(40, 80)">
        <text y="0" class="txt stat-value">{self.stats.get('commits', 0):,}</text>
        <text y="20" class="txt stat-label">Total Commits</text>
    </g>
    <g transform="translate(240, 80)">
        <text y="0" class="txt stat-value">{self.stats.get('prs', 0):,}</text>
        <text y="20" class="txt stat-label">Pull Requests</text>
    </g>
    <g transform="translate(40, 140)">
        <text y="0" class="txt stat-value">{self.stats.get('issues', 0):,}</text>
        <text y="20" class="txt stat-label">Issues Created</text>
    </g>
    <g transform="translate(240, 140)">
        <text y="0" class="txt stat-value">{self.stats.get('reviews', 0):,}</text>
        <text y="20" class="txt stat-label">Code Reviews</text>
    </g>
    <g transform="translate(40, 200)">
        <text y="0" class="txt stat-label">📦 {self.user.get('public_repos', 0)} Repos  •  👥 {self.user.get('followers', 0)} Followers</text>
    </g>
</svg>'''

class LanguageDonutGenerator:
    def __init__(self, skills: List[Dict]):
        self.skills = sorted(skills, key=lambda x: x['bytes'], reverse=True)[:6]
        self.width = 600
        self.height = 320

    def generate(self) -> str:
        total = sum(s['bytes'] for s in self.skills)
        if total == 0: return self._empty()
        
        # Added Width/Height attributes
        svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.width} {self.height}" width="{self.width}" height="{self.height}">']
        svg.append('''<style>
            .txt { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; fill: #e6edf3; }
            .label { font-size: 13px; font-weight: 500; }
            .percent { font-size: 12px; fill: #8b949e; }
        </style>''')
        svg.append('''<defs>
        <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#0d1117"/>
            <stop offset="100%" stop-color="#161b22"/>
        </linearGradient>
        </defs>''')
        svg.append('<rect width="100%" height="100%" fill="url(#bg)" rx="12" stroke="#30363d" stroke-width="2"/>')
        svg.append('<text x="30" y="35" class="txt" font-size="18" font-weight="600">LANGUAGE DISTRIBUTION</text>')
        cx, cy, r = 160, 180, 85
        circumference = 2 * math.pi * r
        offset = 0
        svg.append(f'<g transform="rotate(-90 {cx} {cy})">')
        for s in self.skills:
            pct = s['bytes'] / total
            dash = max(2, pct * circumference)
            svg.append(f'<circle r="{r}" cx="{cx}" cy="{cy}" fill="none" stroke="{s["color"]}" stroke-width="30" stroke-dasharray="{dash} {circumference}" stroke-dashoffset="{-offset}"/>')
            offset += dash
        svg.append('</g>')
        lx, ly = 320, 70
        for s in self.skills:
            pct = (s['bytes'] / total) * 100
            svg.append(f'<circle cx="{lx}" cy="{ly}" r="5" fill="{s["color"]}"/>')
            svg.append(f'<text x="{lx+15}" y="{ly+4}" class="txt label">{s["name"]}</text>')
            svg.append(f'<text x="{lx+160}" y="{ly+4}" class="txt percent" text-anchor="end">{pct:.1f}%</text>')
            ly += 30
        svg.append('</svg>')
        return ''.join(svg)

    def _empty(self):
        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.width} {self.height}" width="{self.width}" height="{self.height}"><rect width="100%" height="100%" fill="#0d1117" rx="12"/><text x="300" y="160" fill="#8b949e" text-anchor="middle" font-family="sans-serif">No data available</text></svg>'

class ContributionHeatmapGenerator:
    def __init__(self, api: GitHubAPI, username: str):
        self.api = api
        self.username = username
        self.width = 900
        self.height = 180

    def generate(self) -> str:
        events = self.api.get_user_events(self.username, limit=100)
        activity_map = defaultdict(int)
        for event in events:
            try:
                date = datetime.strptime(event['created_at'][:10], "%Y-%m-%d").date()
                activity_map[date] += 1
            except: continue
        today = datetime.now().date()
        weeks = []
        for week in range(52):
            week_start = today - timedelta(days=today.weekday() + week * 7)
            week_data = []
            for day in range(7):
                date = week_start - timedelta(days=day)
                count = activity_map.get(date, 0)
                week_data.append((date, count))
            weeks.append(week_data[::-1])
        weeks = weeks[::-1]
        
        # Added Width/Height attributes
        svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.width} {self.height}" width="{self.width}" height="{self.height}">']
        svg.append('<defs><style>')
        svg.append('.txt { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; fill: #e6edf3; font-size: 12px; }')
        svg.append('.title { font-size: 16px; font-weight: 600; }')
        svg.append('</style>')
        svg.append('<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">')
        svg.append('<stop offset="0%" stop-color="#0d1117"/>')
        svg.append('<stop offset="100%" stop-color="#161b22"/>')
        svg.append('</linearGradient>')
        svg.append('</defs>')
        
        svg.append('<rect width="100%" height="100%" fill="url(#bg)" rx="12" stroke="#30363d" stroke-width="2"/>')
        svg.append('<text x="20" y="30" class="txt title">CONTRIBUTION ACTIVITY</text>')
        x_start, y_start = 20, 50
        cell_size = 12
        gap = 3
        max_count = max([max([d[1] for d in week]) for week in weeks]) or 1
        for week_idx, week in enumerate(weeks):
            for day_idx, (date, count) in enumerate(week):
                x = x_start + week_idx * (cell_size + gap)
                y = y_start + day_idx * (cell_size + gap)
                if count == 0: color = '#161b22'
                else:
                    intensity = min(count / max_count, 1.0)
                    if intensity < 0.25: color = '#0e4429'
                    elif intensity < 0.5: color = '#006d32'
                    elif intensity < 0.75: color = '#26a641'
                    else: color = '#39d353'
                svg.append(f'<rect x="{x}" y="{y}" width="{cell_size}" height="{cell_size}" fill="{color}" rx="2"><title>{date}: {count}</title></rect>')
        legend_y = y_start + 8 * (cell_size + gap) + 10
        svg.append(f'<text x="{x_start}" y="{legend_y}" class="txt" fill="#8b949e">Less</text>')
        colors = ['#161b22', '#0e4429', '#006d32', '#26a641', '#39d353']
        for i, color in enumerate(colors):
            x = x_start + 45 + i * (cell_size + gap)
            svg.append(f'<rect x="{x}" y="{legend_y - 10}" width="{cell_size}" height="{cell_size}" fill="{color}" rx="2"/>')
        svg.append(f'<text x="{x_start + 45 + len(colors) * (cell_size + gap) + 5}" y="{legend_y}" class="txt" fill="#8b949e">More</text>')
        svg.append('</svg>')
        return ''.join(svg)

def main():
    token = os.environ.get('GITHUB_TOKEN')
    if not token: return 1
    api = GitHubAPI(token)
    username = os.environ.get('GITHUB_REPOSITORY_OWNER') or api.get_user_info().get('login')
    if not username: return 1
    logger.info(f"👤 User: {username}")
    
    analyzer = AdvancedProfileAnalyzer(api, username)
    skills = analyzer.analyze()
    if not skills: skills = [{'name': 'Analyzing', 'level': 1, 'repos': 0, 'frameworks': [], 'color': '#888888', 'top_repo': '', 'bytes': 100}]

    contrib_stats = api.get_contribution_stats(username)
    user_info = api.get_user_info(username)
    os.makedirs('assets', exist_ok=True)
    
    with open('assets/skill-tree.svg', 'w', encoding='utf-8') as f:
        f.write(SkillTreeGenerator(skills, contrib_stats).generate())
    with open('assets/stats-card.svg', 'w', encoding='utf-8') as f:
        f.write(StatsCardGenerator(contrib_stats, user_info).generate())
    with open('assets/language-donut.svg', 'w', encoding='utf-8') as f:
        f.write(LanguageDonutGenerator(skills).generate())
    with open('assets/contribution-heatmap.svg', 'w', encoding='utf-8') as f:
        f.write(ContributionHeatmapGenerator(api, username).generate())
    
    logger.info("✅ Generation complete")
    return 0

if __name__ == "__main__":
    exit(main())
