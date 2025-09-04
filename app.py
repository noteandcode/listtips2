from flask import Flask, render_template, request, send_file, session
from urllib.parse import urlparse
from urllib import robotparser
from playwright.sync_api import sync_playwright
import pandas as pd
import io

app = Flask(__name__)
app.secret_key = "supersecret"  # szükséges a session-höz

def is_allowed(url):
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
        return rp.can_fetch("*", url)
    except:
        return False

def extract_links(url):
    links = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=60000)
        anchors = page.query_selector_all("a")
        for a in anchors:
            href = a.get_attribute("href")
            if href and href.startswith("http"):
                links.append(href)
        browser.close()
    return links

def filter_links(links, base_url):
    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc

    filtered = []
    for link in links:
        parsed = urlparse(link)
        path = parsed.path.strip("/")
        if path == "":
            if base_domain not in parsed.netloc:
                filtered.append(f"{parsed.scheme}://{parsed.netloc}/")
    return list(set(filtered))

@app.route("/", methods=["GET", "POST"])
def index():
    results = None
    error = None
    no_results = False  # Add this flag
    if request.method == "POST":
        url = request.form.get("url")
        if not url.startswith("http"):
            url = "http://" + url
        if is_allowed(url):
            try:
                links = extract_links(url)
                results = filter_links(links, url)
                session["results"] = results
                # Check if results are empty
                if not results:
                    no_results = True
            except Exception as e:
                error = f"Error extracting links: {e}"
        else:
            error = "Scraping not allowed by robots.txt"
    # Pass no_results to template
    return render_template("index.html", results=results, error=error, no_results=no_results)

@app.route("/download")
def download():
    results = session.get("results")
    if not results:
        return "Nincs exportálható eredmény."
    
    # Excel fájl létrehozása memóriában
    df = pd.DataFrame(results, columns=["Linkek"])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Eredmények")
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="talalatok.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

if __name__ == "__main__":
    app.run(debug=True)
