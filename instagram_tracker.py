import os
import requests
from datetime import datetime, timezone

SHEET_API_URL = os.environ["SHEET_API_URL"].strip()
API_SECRET = os.environ["API_SECRET"].strip()
OPENHANDLE_API_KEY = os.environ["OPENHANDLE_API_KEY"].strip()

OPENHANDLE_BASE_URL = "https://api.openhandle.dev/v1/instagram"


def get_profiles():
    r = requests.post(
        SHEET_API_URL,
        json={
            "action": "profiles",
            "secret": API_SECRET
        },
        timeout=30
    )

    r.raise_for_status()

    try:
        data = r.json()
    except Exception:
        print("Google Sheet API returned:")
        print(r.text[:1000])
        raise

    if not data.get("success"):
        raise Exception(
            data.get("error", "Unable to read profiles")
        )

    return data["profiles"]


def username_from_url(url):
    username = url.rstrip("/").split("/")[-1]

    if "?" in username:
        username = username.split("?")[0]

    return username.strip().lstrip("@")


def openhandle_get(endpoint, username):
    url = (
        f"{OPENHANDLE_BASE_URL}/profiles/"
        f"@{username}/{endpoint}"
    )

    r = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {OPENHANDLE_API_KEY}"
        },
        params={
            "freshness": "24h"
        },
        timeout=30
    )

    r.raise_for_status()

    data = r.json()

    if not isinstance(data, dict):
        raise Exception("Invalid OpenHandle response")

    return data.get("data", [])


def extract_post(item):
    if not isinstance(item, dict):
        return None

    url = (
        item.get("url")
        or item.get("permalink")
        or item.get("link")
    )

    if not url:
        return None

    taken_at = (
        item.get("publishedAt")
        or item.get("takenAt")
        or item.get("createdAt")
        or item.get("timestamp")
        or ""
    )

    return {
        "url": str(url).strip(),
        "taken_at": str(taken_at).strip()
    }


def fetch_posts_and_reels(username):
    results = []

    # One request for posts
    posts = openhandle_get("posts", username)

    # One request for reels
    reels = openhandle_get("reels", username)

    for item in posts + reels:
        post = extract_post(item)

        if post:
            results.append(post)

    # Remove duplicates within the API response
    unique = {}

    for post in results:
        unique[post["url"]] = post

    results = list(unique.values())

    # Oldest -> newest
    def sort_key(post):
        value = post.get("taken_at", "")

        try:
            return datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )
        except Exception:
            return datetime.min.replace(
                tzinfo=timezone.utc
            )

    results.sort(key=sort_key)

    return results


def update_sheet(updates):
    if not updates:
        print("No updates found.")
        return

    r = requests.post(
        SHEET_API_URL,
        json={
            "action": "update",
            "secret": API_SECRET,
            "updates": updates
        },
        timeout=60
    )

    r.raise_for_status()

    data = r.json()

    if not data.get("success"):
        raise Exception(
            data.get("error", "Sheet update failed")
        )

    print("Sheet updated.")
    print("New items:", data.get("added", 0))


def main():
    print("Instagram tracker started.")

    profiles = get_profiles()

    print("Profiles:", len(profiles))

    updates = []

    for profile in profiles:
        name = profile["name"]
        profile_url = profile["profile_url"]
        row = profile["row"]

        print("Checking:", name)

        try:
            username = username_from_url(profile_url)

            posts = fetch_posts_and_reels(username)

            print(
                f"{username}: "
                f"{len(posts)} posts/reels found"
            )

            updates.append({
                "row": row,
                "posts": posts
            })

        except Exception as e:
            print(
                f"ERROR - {name}: {str(e)}"
            )

    update_sheet(updates)

    print("Tracker finished.")


if __name__ == "__main__":
    main()
