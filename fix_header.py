import glob

html_files = ["static/index.html", "static/marketplace.html", "static/checkout.html"]

old_search = """        <div class="qc-search">
          <i class="bi bi-search search-icon"></i>
          <input type="text" class="form-control" placeholder="Search predictive inventory...">
          <button class="cat-btn">Categories <i class="bi bi-chevron-down"></i></button>
        </div>"""

new_search = """        <div class="search-box d-flex align-items-center gap-2">
          <input type="text" id="search-input" class="form-control" placeholder="Search products..." style="border-radius: 20px; min-width: 280px; padding-left: 1rem;">
          <button id="search-btn" class="btn btn-primary" style="height: 40px; border-radius: 20px; padding: 0 1.5rem; font-weight: 600;">Search</button>
        </div>"""

for f in html_files:
    try:
        with open(f, 'r', encoding='utf-8') as file:
            content = file.read()
        content = content.replace(old_search, new_search)
        with open(f, 'w', encoding='utf-8') as file:
            file.write(content)
        print(f"Updated {f}")
    except Exception as e:
        print(f"Failed {f}: {e}")
