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
        self.request_delay = 0.1  # Small delay between requests

    def _check_rate_limit(self) -> bool:
        """Check if we can make a request based on rate limits"""
        current_time = time.time()
        
        # If we've hit reset time, refresh limits
        if current_time >= self.rate_limit_reset:
            self.rate_limit_remaining = 5000  # Conservative estimate
        
        # If we're low on requests, wait
        if self.rate_limit_remaining < 10:
            wait_time = max(self.rate_limit_reset - current_time, 0) + 1
            if wait_time > 0:
                logger.warning(f"  ⚠ Rate limit low ({self.rate_limit_remaining} remaining), waiting {wait_time:.0f}s")
                time.sleep(min(wait_time, 300))  # Max 5 minutes
                self.rate_limit_remaining = 5000
            return True
        return True
    
    def _request(self, endpoint: str, params: Optional[Dict] = None, retry_count: int = 3) -> Any:
        """Smart request handler with exponential backoff and rate limit checking"""
        cache_key = f"{endpoint}:{json.dumps(params or {})}"
        if cache_key in self.cache:
            return self.cache[cache_key], None

        # Check rate limits before making request
        self._check_rate_limit()
        
        # Add small delay to avoid hitting rate limits
        time.sleep(self.request_delay)

        url = f"{self.BASE_URL}/{endpoint}" if not endpoint.startswith('http') else endpoint
        if params and not endpoint.startswith('http'):
            url += '?' + urlencode(params)

        for attempt in range(retry_count):
            try:
                req = Request(url, headers=self.headers)
                with urlopen(req, timeout=30) as response:
                    # Update rate limit info from headers
                    remaining = response.headers.get('X-RateLimit-Remaining')
                    reset = response.headers.get('X-RateLimit-Reset')
                    if remaining:
                        self.rate_limit_remaining = int(remaining)
                    if reset:
                        self.rate_limit_reset = int(reset)
                    
                    try:
                        data = json.loads(response.read().decode())
                    except json.JSONDecodeError:
                        data = {}
                        
                    self.cache[cache_key] = data
                    return data, response.headers
            except HTTPError as e:
                if e.code == 403:
                    # Check if it's a rate limit error
                    reset_time = int(e.headers.get('X-RateLimit-Reset', time.time() + 3600))
                    remaining = int(e.headers.get('X-RateLimit-Remaining', 0))
                    self.rate_limit_remaining = remaining
                    self.rate_limit_reset = reset_time
                    
                    sleep_time = max(reset_time - time.time(), 1) + 1
                    logger.warning(f"  ⚠ Rate limit hit - {remaining} remaining, waiting {sleep_time:.0f}s")
                    time.sleep(min(sleep_time, 300))  # Max 5 minutes wait
                    continue
                elif e.code == 404:
                    return None, None
                elif e.code == 429:  # Too Many Requests
                    retry_after = int(e.headers.get('Retry-After', 60))
                    logger.warning(f"  ⚠ 429 Too Many Requests - waiting {retry_after}s")
                    time.sleep(min(retry_after, 300))
                    continue
                logger.error(f"  ✗ HTTP {e.code}: {e.reason}")
                if attempt == retry_count - 1:
                    return None, None
            except URLError as e:
                logger.error(f"  ✗ Network error: {e.reason}")
                if attempt < retry_count - 1:
                    time.sleep(2 ** attempt)
                else:
                    return None, None
        return None, None

    def get_user_info(self, username: str = None) -> Dict:
        """Fetch user info. If username provided, fetches specific user, else authenticated user."""
        endpoint = f"users/{username}" if username else "user"
        data, _ = self._request(endpoint)
        return data or {}

    def get_all_repos(self, username: str, limit: int = 30) -> List[Dict]:
        """Fetch non-fork repositories with pagination (limited to reduce API calls)"""
        repos = []
        page = 1
        max_pages = 3  # Limit to 3 pages max (300 repos)
        
        while len(repos) < limit and page <= max_pages:
            data, _ = self._request(f"users/{username}/repos", {
                'per_page': 100,
                'page': page,
                'type': 'owner',
                'sort': 'updated',
                'direction': 'desc'
            })
            if not data:
                break
            repos.extend([r for r in data if not r.get('fork', False)])
            if len(data) < 100:
                break
            page += 1
        
        # Return only the most recently updated repos
        return repos[:limit]

    def get_repo_languages(self, owner: str, repo: str) -> Dict[str, int]:
        """Fetch language statistics"""
        data, _ = self._request(f"repos/{owner}/{repo}/languages")
        return data or {}

    def get_repo_contents(self, owner: str, repo: str, path: str = "") -> List[Dict]:
        """Fetch repository contents"""
        data, _ = self._request(f"repos/{owner}/{repo}/contents/{path}")
        return data if isinstance(data, list) else []

    def get_commits(self, owner: str, repo: str, since: str = None) -> List[Dict]:
        """Fetch recent commits"""
        params = {'per_page': 100}
        if since:
            params['since'] = since
        data, _ = self._request(f"repos/{owner}/{repo}/commits", params)
        return data or []

    def get_user_events(self, username: str, limit: int = 100) -> List[Dict]:
        """Fetch user activity events (limited to reduce API calls)"""
        data, _ = self._request(f"users/{username}/events/public", {'per_page': min(limit, 100)})
        return (data or [])[:limit]

    def get_contribution_stats(self, username: str) -> Dict[str, int]:
        """Fetch contribution statistics with reduced API calls"""
        stats = {'commits': 0, 'prs': 0, 'issues': 0, 'reviews': 0, 'stars_given': 0}
        
        # Only fetch PRs and Issues (skip reviews to save API calls)
        # Search API is expensive, so we limit usage
        try:
            # PRs
            d, _ = self._request("search/issues", {'q': f'author:{username} type:pr is:merged', 'per_page': 1})
            if d:
                stats['prs'] = min(d.get('total_count', 0), 5000)
            
            # Issues
            d, _ = self._request("search/issues", {'q': f'author:{username} type:issue', 'per_page': 1})
            if d:
                stats['issues'] = min(d.get('total_count', 0), 5000)
        except Exception as e:
            logger.warning(f"  ⚠ Could not fetch contribution stats: {e}")
        
        # Estimate commits from repo count (avoid expensive commit API calls)
        # This is an approximation to avoid rate limits
        repos = self.get_all_repos(username, limit=10)
        stats['commits'] = len(repos) * 50  # Rough estimate: 50 commits per repo
        
        return stats


class AdvancedProfileAnalyzer:
    """Deep profile analysis with tech stack detection"""

    TECH_DETECTION = {
        'Python': {
            'files': ['requirements.txt', 'setup.py', 'pyproject.toml', 'pipfile', 'poetry.lock', 'conda.yml'],
            'frameworks': {
                'Django': ['django', 'manage.py', 'wsgi.py', 'settings.py'],
                'Flask': ['flask', 'app.py', 'application.py'],
                'FastAPI': ['fastapi', 'main.py', 'api'],
                'Pandas': ['pandas', 'dataframe', 'pd.'],
                'PyTorch': ['torch', 'pytorch', 'nn.module'],
                'TensorFlow': ['tensorflow', 'tf.', 'keras'],
                'Streamlit': ['streamlit', 'st.'],
                'Scrapy': ['scrapy', 'spider'],
            }
        },
        'JavaScript': {
            'files': ['package.json', 'package-lock.json', 'yarn.lock'],
            'frameworks': {
                'React': ['react', 'jsx', 'tsx', 'create-react-app'],
                'Vue': ['vue', 'nuxt'],
                'Angular': ['angular', '@angular'],
                'Next.js': ['next', 'next.config'],
                'Express': ['express', 'app.listen'],
                'Node.js': ['node', 'npm', 'server.js'],
            }
        },
        'TypeScript': {
            'files': ['tsconfig.json', 'package.json'],
            'frameworks': {
                'React': ['react', 'tsx'],
                'Angular': ['angular.json'],
                'NestJS': ['nest', '@nestjs'],
                'Vue': ['vue', 'composition-api'],
            }
        },
        'Java': {
            'files': ['pom.xml', 'build.gradle', 'settings.gradle', 'mvnw'],
            'frameworks': {
                'Spring Boot': ['spring-boot', '@springbootapplication'],
                'Maven': ['pom.xml', 'maven'],
                'Gradle': ['build.gradle', 'gradle'],
                'Hibernate': ['hibernate', 'jpa'],
                'Android': ['android', 'androidmanifest'],
            }
        },
        'Go': {
            'files': ['go.mod', 'go.sum'],
            'frameworks': {
                'Gin': ['gin-gonic', 'gin'],
                'Echo': ['echo', 'labstack'],
                'Fiber': ['fiber', 'gofiber'],
            }
        },
        'Rust': {
            'files': ['cargo.toml', 'cargo.lock'],
            'frameworks': {
                'Actix': ['actix-web'],
                'Rocket': ['rocket'],
                'Tokio': ['tokio'],
            }
        },
        'PHP': {
            'files': ['composer.json', 'composer.lock'],
            'frameworks': {
                'Laravel': ['laravel', 'artisan'],
                'Symfony': ['symfony'],
                'WordPress': ['wordpress', 'wp-'],
            }
        },
        'C#': {
            'files': ['.csproj', '.sln'],
            'frameworks': {
                '.NET': ['dotnet', 'netcore'],
                'ASP.NET': ['asp.net', 'mvc'],
                'Unity': ['unity', 'monobehaviour'],
            }
        },
        'Ruby': {
            'files': ['gemfile', 'gemfile.lock'],
            'frameworks': {
                'Rails': ['rails', 'activerecord'],
                'Sinatra': ['sinatra'],
            }
        }
    }

    LANGUAGE_COLORS = {
        'Python': '#3572A5', 'Java': '#b07219', 'JavaScript': '#f1e05a',
        'TypeScript': '#2b7489', 'C++': '#f34b7d', 'HTML': '#e34c26',
        'CSS': '#563d7c', 'C#': '#178600', 'Go': '#00ADD8',
        'Rust': '#dea584', 'PHP': '#4F5D95', 'Ruby': '#701516',
        'Swift': '#ffac45', 'Kotlin': '#A97BFF', 'Dart': '#00B4AB',
        'Shell': '#89e051', 'Dockerfile': '#384d54'
    }

    def __init__(self, api: GitHubAPI, username: str):
        self.api = api
        self.username = username
        self.skills = defaultdict(lambda: {
            'bytes': 0,
            'repos': 0,
            'commits': 0,
            'score': 0,
            'frameworks': defaultdict(int),
            'top_repo': ('', 0),
            'recent_activity': 0
        })

    def analyze(self) -> List[Dict]:
        """Comprehensive profile analysis (optimized to reduce API calls)"""
        logger.info(f"🚀 Analyzing profile: {self.username}")
        
        # Limit repos to reduce API calls
        repos = self.api.get_all_repos(self.username, limit=30)
        logger.info(f"📂 Processing {len(repos)} repositories (limited to reduce API calls)")

        contribution_stats = self.api.get_contribution_stats(self.username)
        
        # Analyze each repository
        for idx, repo in enumerate(repos):
            if idx % 10 == 0:
                logger.info(f"  Progress: {idx}/{len(repos)}")
            
            self._analyze_repo(repo, contribution_stats)

        # Process and rank skills
        return self._process_skills(contribution_stats)

    def _analyze_repo(self, repo: Dict, contrib_stats: Dict):
        """Deep dive into single repository (optimized to reduce API calls)"""
        name = repo['name']
        size = repo.get('size', 0)
        
        # Skip tiny repos
        if size < 10:
            return

        # Get languages (this is essential)
        langs = self.api.get_repo_languages(self.username, name)
        
        # Skip file structure scanning to save API calls
        # Use repo description and name for framework detection instead
        files = []
        repo_text = (repo.get('description', '') or '').lower() + ' ' + name.lower()

        # Calculate recency multiplier
        pushed_at = repo.get('pushed_at')
        recency = 0.5
        if pushed_at:
            try:
                date = datetime.strptime(pushed_at[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
                days_old = (datetime.now(timezone.utc) - date).days
                recency = max(0.3, 1.0 - (days_old / 730))  # 2-year decay
            except:
                pass

        # Process each language
        for lang, byte_count in langs.items():
            if byte_count < 1000:  # Skip trivial amounts
                continue

            self.skills[lang]['bytes'] += byte_count
            self.skills[lang]['repos'] += 1
            self.skills[lang]['recent_activity'] += recency

            # Track top repo
            if byte_count > self.skills[lang]['top_repo'][1]:
                self.skills[lang]['top_repo'] = (name, byte_count)

            # Calculate weighted score
            base_score = math.log(byte_count + 1) * 5
            repo_bonus = math.log(size + 1) * 2
            star_bonus = math.log(repo.get('stargazers_count', 0) + 1) * 3
            
            total_score = (base_score + repo_bonus + star_bonus) * recency
            self.skills[lang]['score'] += total_score

            # Detect frameworks (using repo metadata instead of file scanning)
            if lang in self.TECH_DETECTION:
                repo_text = name.lower() + ' ' + (repo.get('description') or '').lower()
                self._detect_frameworks(lang, files, repo_text)

    def _detect_frameworks(self, lang: str, files: List[str], text: str):
        """Detect frameworks and tools (optimized - text-based only to save API calls)"""
        tech = self.TECH_DETECTION[lang]
        
        # Text-based detection only (no file scanning to save API calls)
        for framework, keywords in tech['frameworks'].items():
            weight = 0
            
            # Text-based detection (repo name and description)
            if any(kw in text for kw in keywords):
                weight += 10  # Reduced weight since we're not checking files
            
            if weight > 0:
                self.skills[lang]['frameworks'][framework] += weight

    def _process_skills(self, contrib_stats: Dict) -> List[Dict]:
        """Process and rank all detected skills"""
        processed = []
        total_score = sum(s['score'] for s in self.skills.values()) or 1
        
        # Add contribution bonus
        contrib_bonus = (
            contrib_stats.get('prs', 0) * 8 +
            contrib_stats.get('issues', 0) * 3 +
            contrib_stats.get('reviews', 0) * 5 +
            contrib_stats.get('commits', 0) * 0.5
        )

        for lang, data in self.skills.items():
            if data['bytes'] < 1000:  # Skip minimal usage
                continue

            # Calculate final level (1-10)
            normalized_score = (data['score'] / total_score) * 100
            contribution_score = contrib_bonus / max(len(self.skills), 1)
            activity_score = data['recent_activity'] * 10
            
            final_score = normalized_score + contribution_score + activity_score
            level = min(10, max(1, int(math.sqrt(final_score) * 1.2)))

            # Get top frameworks
            top_frameworks = sorted(
                data['frameworks'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]

            processed.append({
                'name': lang,
                'level': level,
                'repos': data['repos'],
                'bytes': data['bytes'],
                'frameworks': [fw[0] for fw in top_frameworks],
                'top_repo': data['top_repo'][0],
                'color': self.LANGUAGE_COLORS.get(lang, '#888888'),
                'score': final_score
            })

        # Sort by level and bytes
        return sorted(processed, key=lambda x: (x['level'], x['bytes']), reverse=True)[:12]


class ContributionHeatmapGenerator:
    """Generates a GitHub-style contribution heatmap"""
    
    def __init__(self, api: GitHubAPI, username: str):
        self.api = api
        self.username = username
        self.width = 900
        self.height = 180

    def generate(self) -> str:
        """Create contribution heatmap SVG"""
        logger.info("📊 Generating contribution heatmap")
        
        # Get limited events to reduce API calls
        events = self.api.get_user_events(self.username, limit=100)
        
        # Process events by date
        activity_map = defaultdict(int)
        for event in events:
            try:
                date = datetime.strptime(event['created_at'][:10], "%Y-%m-%d").date()
                activity_map[date] += 1
            except:
                continue

        # Generate last 52 weeks
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

        # Build SVG
        svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.width} {self.height}" width="{self.width}" height="{self.height}">']
        svg.append('<defs><style>')
        svg.append('@import url("https://fonts.googleapis.com/css2?family=Segoe+UI:wght@400;600&display=swap");')
        svg.append('.txt { font-family: "Segoe UI", sans-serif; fill: #e6edf3; font-size: 12px; }')
        svg.append('.title { font-size: 16px; font-weight: 600; }')
        svg.append('</style></defs>')
        svg.append('<rect width="100%" height="100%" fill="#0d1117" rx="10"/>')
        svg.append('<rect width="100%" height="100%" fill="none" stroke="#30363d" stroke-width="2" rx="10"/>')
        svg.append('<text x="20" y="30" class="txt title">CONTRIBUTION ACTIVITY</text>')

        # Draw heatmap
        x_start, y_start = 20, 50
        cell_size = 12
        gap = 3

        max_count = max([max([d[1] for d in week]) for week in weeks]) or 1

        for week_idx, week in enumerate(weeks):
            for day_idx, (date, count) in enumerate(week):
                x = x_start + week_idx * (cell_size + gap)
                y = y_start + day_idx * (cell_size + gap)
                
                # Color intensity based on activity
                if count == 0:
                    color = '#161b22'
                else:
                    intensity = min(count / max_count, 1.0)
                    if intensity < 0.25:
                        color = '#0e4429'
                    elif intensity < 0.5:
                        color = '#006d32'
                    elif intensity < 0.75:
                        color = '#26a641'
                    else:
                        color = '#39d353'
                
                svg.append(f'<rect x="{x}" y="{y}" width="{cell_size}" height="{cell_size}" fill="{color}" rx="2">')
                svg.append(f'<title>{date}: {count} contributions</title>')
                svg.append('</rect>')

        # Add legend
        legend_y = y_start + 8 * (cell_size + gap) + 10
        svg.append(f'<text x="{x_start}" y="{legend_y}" class="txt" fill="#8b949e">Less</text>')
        
        colors = ['#161b22', '#0e4429', '#006d32', '#26a641', '#39d353']
        for i, color in enumerate(colors):
            x = x_start + 45 + i * (cell_size + gap)
            svg.append(f'<rect x="{x}" y="{legend_y - 10}" width="{cell_size}" height="{cell_size}" fill="{color}" rx="2"/>')
        
        svg.append(f'<text x="{x_start + 45 + len(colors) * (cell_size + gap) + 5}" y="{legend_y}" class="txt" fill="#8b949e">More</text>')

        svg.append('</svg>')
        return ''.join(svg)


class SkillTreeGenerator:
    """Modern skill tree with enhanced visuals"""
    
    def __init__(self, skills: List[Dict], contrib_stats: Dict):
        self.skills = skills
        self.contrib_stats = contrib_stats
        self.width = 900
        self.height = 200 + len(skills) * 95

    def generate(self) -> str:
        """Generate skill tree SVG"""
        logger.info("🎨 Generating skill tree visualization")
        
        return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.width} {self.height}" width="{self.width}" height="{self.height}">
    <defs>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&display=swap');
            .txt {{ font-family: 'JetBrains Mono', monospace; fill: #e6edf3; }}
            .title {{ font-size: 32px; font-weight: 700; letter-spacing: 2px; }}
            .subtitle {{ font-size: 13px; fill: #8b949e; }}
            .lang {{ font-size: 17px; font-weight: 600; }}
            .stat {{ font-size: 12px; fill: #8b949e; }}
            .framework {{ font-size: 11px; fill: #79c0ff; }}
            .bar-bg {{ fill: #161b22; stroke: #30363d; stroke-width: 1; rx: 5; }}
            .glow {{ filter: drop-shadow(0 0 8px rgba(249, 38, 114, 0.6)); }}
            .pulse {{ animation: pulse 2s ease-in-out infinite; }}
            @keyframes pulse {{
                0%, 100% {{ opacity: 1; }}
                50% {{ opacity: 0.6; }}
            }}
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
        <text x="0" y="50" class="txt subtitle">
            {self.contrib_stats.get('prs', 0)} Pull Requests • 
            {self.contrib_stats.get('commits', 0)} Commits • 
            {self.contrib_stats.get('reviews', 0)} Reviews
        </text>
        <line x1="0" y1="70" x2="{self.width - 80}" y2="70" stroke="#30363d" stroke-width="2"/>
    </g>
    
    {self._render_skills()}
</svg>'''

    def _render_skills(self) -> str:
        """Render skill nodes"""
        nodes = []
        y_offset = 150
        
        for idx, skill in enumerate(self.skills):
            level = skill['level']
            bar_width = (level / 10) * 350
            
            frameworks = ' • '.join(skill['frameworks'][:3]) if skill['frameworks'] else 'Core'
            repo_info = f"Top: {skill['top_repo']}" if skill['top_repo'] else f"{skill['repos']} repos"
            
            # Determine tier
            if level >= 8:
                tier = "⭐ EXPERT"
                tier_color = "#f92672"
            elif level >= 6:
                tier = "◆ ADVANCED"
                tier_color = "#a626a4"
            elif level >= 4:
                tier = "● INTERMEDIATE"
                tier_color = "#61afef"
            else:
                tier = "○ LEARNING"
                tier_color = "#8b949e"
            
            nodes.append(f'''
    <g transform="translate(40, {y_offset})">
        <circle cx="18" cy="18" r="10" fill="{skill['color']}" class="glow"/>
        <circle cx="18" cy="18" r="6" fill="{skill['color']}" opacity="0.5" class="pulse"/>
        <line x1="18" y1="28" x2="18" y2="70" stroke="#30363d" stroke-width="2" stroke-dasharray="3,3"/>
        
        <text x="45" y="24" class="txt lang" fill="{skill['color']}">{skill['name']}</text>
        <text x="{self.width - 180}" y="24" class="txt stat" fill="{tier_color}" text-anchor="end">{tier}</text>
        <text x="{self.width - 80}" y="24" class="txt stat" text-anchor="end">LVL {level}</text>
        
        <rect x="45" y="35" width="350" height="10" class="bar-bg"/>
        <rect x="45" y="35" width="{bar_width}" height="10" fill="{skill['color']}" rx="5" opacity="0.85">
            <animate attributeName="width" from="0" to="{bar_width}" dur="1.2s" fill="freeze"/>
        </rect>
        
        <text x="45" y="62" class="txt framework">{frameworks}</text>
        <text x="{self.width - 80}" y="62" class="txt stat" text-anchor="end">{repo_info}</text>
    </g>
            ''')
            y_offset += 95

        return '\n'.join(nodes)


class LanguageDonutGenerator:
    """Enhanced donut chart with percentages"""
    
    def __init__(self, skills: List[Dict]):
        self.skills = sorted(skills, key=lambda x: x['bytes'], reverse=True)[:10]
        self.width = 600
        self.height = 320

    def generate(self) -> str:
        """Generate donut chart SVG"""
        logger.info("📈 Generating language distribution chart")
        
        total_bytes = sum(s['bytes'] for s in self.skills)
        if total_bytes == 0:
            return self._empty_state()

        svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.width} {self.height}" width="{self.width}" height="{self.height}">']
        svg.append('<defs><style>')
        svg.append('@import url("https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&display=swap");')
        svg.append('.txt { font-family: "JetBrains Mono", monospace; fill: #e6edf3; }')
        svg.append('.title { font-size: 18px; font-weight: 600; }')
        svg.append('.label { font-size: 13px; font-weight: 500; }')
        svg.append('.percent { font-size: 12px; fill: #8b949e; }')
        svg.append('</style>')
        svg.append('<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">')
        svg.append('<stop offset="0%" stop-color="#0d1117"/>')
        svg.append('<stop offset="100%" stop-color="#161b22"/>')
        svg.append('</linearGradient></defs>')
        
        svg.append('<rect width="100%" height="100%" fill="url(#bg)" rx="12"/>')
        svg.append('<rect width="100%" height="100%" fill="none" stroke="#30363d" stroke-width="2" rx="12"/>')
        svg.append('<text x="30" y="35" class="txt title">LANGUAGE DISTRIBUTION</text>')

        # Draw donut
        cx, cy, radius = 160, 180, 85
        circumference = 2 * math.pi * radius
        current_offset = 0

        svg.append(f'<g transform="rotate(-90 {cx} {cy})">')
        for skill in self.skills:
            percent = skill['bytes'] / total_bytes
            arc_length = percent * circumference
            
            if arc_length < 2:
                arc_length = 2  # Minimum visibility
            
            svg.append(
                f'<circle r="{radius}" cx="{cx}" cy="{cy}" fill="transparent" '
                f'stroke="{skill["color"]}" stroke-width="30" '
                f'stroke-dasharray="{arc_length} {circumference}" '
                f'stroke-dashoffset="{-current_offset}"/>'
            )
            current_offset += arc_length
        svg.append('</g>')

        # Center label
        svg.append(f'<text x="{cx}" y="{cy - 5}" class="txt label" text-anchor="middle" font-size="16px">TOTAL</text>')
        svg.append(f'<text x="{cx}" y="{cy + 15}" class="txt percent" text-anchor="middle" font-size="14px">{len(self.skills)} langs</text>')

        # Legend
        legend_x, legend_y = 320, 70
        for skill in self.skills:
            percent = (skill['bytes'] / total_bytes) * 100
            
            svg.append(f'<circle cx="{legend_x}" cy="{legend_y}" r="5" fill="{skill["color"]}"/>')
            svg.append(f'<text x="{legend_x + 15}" y="{legend_y + 4}" class="txt label">{skill["name"]}</text>')
            svg.append(f'<text x="{legend_x + 180}" y="{legend_y + 4}" class="txt percent" text-anchor="end">{percent:.1f}%</text>')
            svg.append(f'<text x="{legend_x + 260}" y="{legend_y + 4}" class="txt percent" text-anchor="end">{skill["repos"]} repos</text>')
            
            legend_y += 24

        svg.append('</svg>')
        return ''.join(svg)

    def _empty_state(self) -> str:
        """Fallback for empty data"""
        return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.width} {self.height}">
<rect width="100%" height="100%" fill="#0d1117" rx="12"/>
<text x="50%" y="50%" fill="#8b949e" text-anchor="middle" font-family="monospace" font-size="14px">
No language data available
</text>
</svg>'''


class StatsCardGenerator:
    """Generate comprehensive stats card"""
    
    def __init__(self, contrib_stats: Dict, user_info: Dict):
        self.stats = contrib_stats
        self.user_info = user_info
        self.width = 480
        self.height = 240

    def generate(self) -> str:
        """Create stats card SVG"""
        logger.info("📊 Generating stats card")
        
        total_repos = self.user_info.get('public_repos', 0)
        followers = self.user_info.get('followers', 0)
        following = self.user_info.get('following', 0)
        
        return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.width} {self.height}">
    <defs>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&display=swap');
            .txt {{ font-family: 'JetBrains Mono', monospace; fill: #e6edf3; }}
            .title {{ font-size: 16px; font-weight: 600; }}
            .stat-value {{ font-size: 28px; font-weight: 700; fill: #f92672; }}
            .stat-label {{ font-size: 12px; fill: #8b949e; }}
        </style>
        <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="#0d1117"/>
            <stop offset="100%" stop-color="#161b22"/>
        </linearGradient>
    </defs>
    
    <rect width="100%" height="100%" fill="url(#bg)" rx="12"/>
    <rect width="100%" height="100%" fill="none" stroke="#30363d" stroke-width="2" rx="12"/>
    
    <text x="24" y="32" class="txt title">CONTRIBUTION STATS</text>
    <line x1="24" y1="45" x2="{self.width - 24}" y2="45" stroke="#30363d" stroke-width="1"/>
    
    <g transform="translate(40, 80)">
        <text x="0" y="0" class="txt stat-value">{self.stats.get('commits', 0):,}</text>
        <text x="0" y="20" class="txt stat-label">Total Commits</text>
    </g>
    
    <g transform="translate(240, 80)">
        <text x="0" y="0" class="txt stat-value">{self.stats.get('prs', 0):,}</text>
        <text x="0" y="20" class="txt stat-label">Pull Requests</text>
    </g>
    
    <g transform="translate(40, 140)">
        <text x="0" y="0" class="txt stat-value">{self.stats.get('issues', 0):,}</text>
        <text x="0" y="20" class="txt stat-label">Issues Created</text>
    </g>
    
    <g transform="translate(240, 140)">
        <text x="0" y="0" class="txt stat-value">{self.stats.get('reviews', 0):,}</text>
        <text x="0" y="20" class="txt stat-label">Code Reviews</text>
    </g>
    
    <g transform="translate(40, 200)">
        <text x="0" y="0" class="txt stat-label">📦 {total_repos} Repos  •  👥 {followers} Followers  •  {following} Following</text>
    </g>
</svg>'''


def main():
    """Main execution"""
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        logger.error("❌ GITHUB_TOKEN environment variable required")
        return 1

    try:
        # Initialize
        api = GitHubAPI(token)
        
        # FIX: Try to get username from environment first (GitHub Actions standard)
        # This prevents the script from using the bot's username (github-actions[bot])
        username = os.environ.get('GITHUB_REPOSITORY_OWNER')
        
        if not username:
            # Fallback for local testing
            logger.info("ℹ️  GITHUB_REPOSITORY_OWNER not set, falling back to API user")
            user_info = api.get_user_info()
            username = user_info.get('login')
        else:
            logger.info(f"ℹ️  Using detected username: {username}")
            # Still fetch user info for stats card
            user_info = api.get_user_info(username)
        
        if not username:
            logger.error("❌ Failed to identify user")
            return 1

        logger.info(f"👤 Authenticated for: {username}")

        # Analyze profile
        analyzer = AdvancedProfileAnalyzer(api, username)
        skills = analyzer.analyze()
        
        if not skills:
            logger.warning("⚠ No skills detected, using placeholder")
            skills = [{
                'name': 'Analyzing',
                'level': 1,
                'repos': 0,
                'frameworks': [],
                'color': '#888888',
                'top_repo': '',
                'bytes': 100
            }]

        # Get contribution stats
        contrib_stats = api.get_contribution_stats(username)
        
        # Create output directory
        os.makedirs('assets', exist_ok=True)

        # Generate visualizations
        logger.info("🎨 Generating visualizations...")
        
        # 1. Skill Tree
        skill_tree = SkillTreeGenerator(skills, contrib_stats).generate()
        with open('assets/skill-tree.svg', 'w', encoding='utf-8') as f:
            f.write(skill_tree)
        
        # 2. Language Donut
        language_donut = LanguageDonutGenerator(skills).generate()
        with open('assets/language-donut.svg', 'w', encoding='utf-8') as f:
            f.write(language_donut)
        
        # 3. Contribution Heatmap
        heatmap = ContributionHeatmapGenerator(api, username).generate()
        with open('assets/contribution-heatmap.svg', 'w', encoding='utf-8') as f:
            f.write(heatmap)
        
        # 4. Stats Card
        stats_card = StatsCardGenerator(contrib_stats, user_info).generate()
        with open('assets/stats-card.svg', 'w', encoding='utf-8') as f:
            f.write(stats_card)

        logger.info(f"✅ Successfully generated all assets for {username}")
        logger.info(f"   📊 {len(skills)} skills detected")
        logger.info(f"   📈 {contrib_stats.get('commits', 0)} commits tracked")
        return 0

    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
