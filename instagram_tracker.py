import os
import requests
import instaloader
from datetime import timezone

SHEET_API_URL = os.environ["SHEET_API_URL"].strip()
API_SECRET = os.environ["API_SECRET"].strip()

L = instaloader.Instaloader(
    download_pictures=False,
    download_videos=False,
    download_video_thumbnails=False,
    save_metadata=False,
    compress_json=False,
    quiet=True
)


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

    return username


def fetch_posts(username, limit=20):

    profile = instaloader.Profile.from_username(
        L.context,
        username
    )

    results = []

    for post in profile.get_posts():

        url = f"https://www.instagram.com/p/{post.shortcode}/"

        results.append({
            "url": url,
            "taken_at": post.date_utc.replace(
                tzinfo=timezone.utc
            ).isoformat()
        })

        if len(results) >= limit:
            break

    results.reverse()

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

            posts = fetch_posts(username, 20)

            print(
                f"{username}: {len(posts)} posts/reels found"
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
