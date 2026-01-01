# 🚀 Ultimate GitHub Profile Setup Guide

## 📋 Prerequisites

- A GitHub account
- A repository named **exactly** as your username (e.g., `Vedant1434/Vedant1434`)
- GitHub Actions enabled (should be by default)

## 🎯 Quick Setup (5 Minutes)

### Step 1: Create Your Profile Repository

1. Go to https://github.com/new
2. Repository name: **Your exact GitHub username** (e.g., `Vedant1434`)
3. ✅ Check "Public"
4. ✅ Check "Add a README file"
5. Click "Create repository"

### Step 2: Add the Scripts

Create the following directory structure in your repository:

```
Vedant1434/
├── .github/
│   └── workflows/
│       ├── update-profile.yml
│       └── snake.yml
├── scripts/
│   └── generate_skill_tree.py
├── assets/
│   └── (SVG files will be auto-generated here)
└── README.md
```

**Create each file:**

1. **`.github/workflows/update-profile.yml`**
   - Copy the workflow YAML from the artifact above

2. **`.github/workflows/snake.yml`**
   - Copy the snake workflow YAML

3. **`scripts/generate_skill_tree.py`**
   - Copy the complete Python script

4. **`README.md`**
   - Copy and customize the ultimate README template
   - Replace `Vedant1434` with your username
   - Update social links
   - Customize the "About Me" section

5. **Create `assets/` directory**
   ```bash
   mkdir assets
   ```

### Step 3: Customize Your Profile

Edit `README.md` and update:

1. **Your Name & Title**
   ```markdown
   # 👋 Hey, I'm [Your Name]
   ```

2. **About Me Section**
   - Update role, focus areas, languages
   - Modify the Python class example

3. **Social Links**
   ```markdown
   [![LinkedIn](link-to-your-linkedin)]
   [![Twitter](link-to-your-twitter)]
   ```

4. **Portfolio URL** (if you have one)

5. **Featured Projects**
   - Replace with your actual repository names

### Step 4: Configure GitHub Actions

1. Go to your repository Settings
2. Navigate to: **Actions** → **General**
3. Under "Workflow permissions":
   - ✅ Select **"Read and write permissions"**
   - ✅ Check **"Allow GitHub Actions to create and approve pull requests"**
4. Click **Save**

### Step 5: Initial Run

**Option A: Manual Trigger**
1. Go to **Actions** tab
2. Select "🚀 Update GitHub Profile"
3. Click **"Run workflow"**
4. Wait 1-2 minutes for completion

**Option B: Push Changes**
```bash
git add .
git commit -m "feat: setup ultimate profile"
git push
```

The workflow will automatically run on push!

## ✨ Features Overview

### 🎮 Skill Tree
- **Auto-detects** languages from all your repositories
- **Scans files** for framework identification (pom.xml, package.json, etc.)
- **Calculates levels** based on code volume, commits, and activity
- **Updates daily** via GitHub Actions

### 📊 Language Distribution
- **Donut chart** showing language usage percentages
- **Repository counts** per language
- **Color-coded** using GitHub's official language colors

### 🔥 Contribution Heatmap
- **52-week** activity visualization
- **GitHub-style** color intensity
- **Hover tooltips** with contribution counts

### 📈 Stats Card
- **Total commits** tracked
- **Pull requests** merged
- **Issues** created
- **Code reviews** completed

### 🐍 Contribution Snake
- **Animated** contribution graph
- **Multiple themes** available
- **Automatically** updates every 12 hours

## 🔧 Advanced Customization

### Modify Update Frequency

Edit `.github/workflows/update-profile.yml`:

```yaml
on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours
    # Change to:
    - cron: '0 0 * * *'    # Daily at midnight
    # Or:
    - cron: '0 */3 * * *'  # Every 3 hours
```

### Add More Languages

Edit `scripts/generate_skill_tree.py`, add to `TECH_DETECTION`:

```python
'YourLanguage': {
    'files': ['config.yml', 'package.ext'],
    'frameworks': {
        'YourFramework': ['keyword1', 'keyword2'],
    }
}
```

### Change Color Scheme

In `generate_skill_tree.py`, modify `LANGUAGE_COLORS`:

```python
LANGUAGE_COLORS = {
    'Python': '#YOUR_COLOR',
    # ...
}
```

### Exclude Repositories

If you want to exclude certain repos from analysis, modify the script:

```python
def get_all_repos(self, username: str) -> List[Dict]:
    exclude_list = ['repo-name-to-exclude', 'another-repo']
    repos = []
    # ... existing code ...
    return [r for r in repos if r['name'] not in exclude_list]
```

## 🐛 Troubleshooting

### Issue: Workflow fails with "Permission denied"
**Solution:** 
1. Go to Settings → Actions → General
2. Enable "Read and write permissions"
3. Re-run the workflow

### Issue: No SVGs generated
**Solution:**
1. Check Actions logs for errors
2. Ensure `assets/` directory exists
3. Verify Python script has no syntax errors

### Issue: Stats show 0 everywhere
**Solution:**
1. Make sure your repositories are **public**
2. Check that you have recent activity (commits, PRs)
3. Wait 24 hours for GitHub's API to update

### Issue: Skill tree shows only "Scanning..."
**Solution:**
1. Ensure you have at least one **non-fork** repository
2. Check that repositories have actual code (not just README)
3. Verify GITHUB_TOKEN has correct permissions

### Issue: Snake not showing
**Solution:**
1. Wait for the snake workflow to complete (check Actions tab)
2. Ensure the `output` branch was created
3. Update the snake URL in README to use your username

## 📚 Additional Resources

### GitHub Actions Documentation
- [Workflow syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
- [Environment variables](https://docs.github.com/en/actions/learn-github-actions/variables)

### SVG Resources
- [MDN SVG Guide](https://developer.mozilla.org/en-US/docs/Web/SVG)
- [SVG Optimization](https://jakearchibald.github.io/svgomg/)

### GitHub API
- [REST API Docs](https://docs.github.com/en/rest)
- [Rate Limiting](https://docs.github.com/en/rest/overview/resources-in-the-rest-api#rate-limiting)

## 🎨 Customization Ideas

### 1. Add WakaTime Stats
```markdown
<!--START_SECTION:waka-->
<!--END_SECTION:waka-->
```
Setup: https://github.com/anmol098/waka-readme-stats

### 2. Add Blog Posts
Use: https://github.com/gautamkrishnar/blog-post-workflow

### 3. Add Spotify Now Playing
Use: https://github.com/kittinan/spotify-github-profile

### 4. Add Visitor Counter
```markdown
![](https://komarev.com/ghpvc/?username=YOUR_USERNAME)
```

## 💡 Pro Tips

1. **Pin Your Best Repos** - They'll appear in the featured projects section
2. **Write Good READMEs** - They help with framework detection
3. **Use Topics** - Add topics to your repos for better categorization
4. **Stay Active** - Regular commits keep your heatmap vibrant
5. **Star Repos** - Show support and discover new projects

## 📝 Maintenance

### Weekly Tasks
- ✅ Check Actions logs for any failures
- ✅ Review generated SVGs for accuracy
- ✅ Update featured projects if needed

### Monthly Tasks
- ✅ Update social links if changed
- ✅ Review and update "Current Focus" section
- ✅ Add new skills/frameworks to detection list
- ✅ Update the "About Me" section

## 🤝 Contributing

Found a bug or have an idea? Feel free to:
1. Open an issue in your repository
2. Fork and improve the script
3. Share your customizations with the community

## 📄 License

This setup is free to use and modify. Attribution appreciated but not required!

---

## 🎉 Final Checklist

Before going live:

- [ ] Repository name matches username exactly
- [ ] Workflows are in `.github/workflows/`
- [ ] Python script is in `scripts/`
- [ ] `assets/` directory exists
- [ ] README.md is customized
- [ ] Workflow permissions are set correctly
- [ ] Initial workflow run completed successfully
- [ ] All 4 SVG files generated in `assets/`
- [ ] Social links are updated
- [ ] Featured projects are correct

## 🚀 You're All Set!

Your ultimate GitHub profile is now live! Share it with:
- Twitter: Tweet your profile URL
- LinkedIn: Update your "Featured" section
- Dev.to: Write about your setup
- Reddit: r/github, r/webdev

**Remember:** The profile updates automatically every day, so your stats will always be fresh!

---

<div align="center">

### Need Help?

💬 **Questions?** Open an issue  
⭐ **Found this useful?** Star the repo  
🔗 **Share** with fellow developers!

</div>