#!/usr/bin/env python3
"""
Publish out/reel.mp4 with out/caption.txt to Instagram Reels (and, when allowed, the Facebook Page).

Environment (GitHub secrets / variables):
  META_PAGE_TOKEN   System-user (or Page) token
  IG_USER_ID        Instagram professional account id (instagram_business_account.id)
  FB_PAGE_ID        Facebook Page id (optional; Facebook posting needs pages_manage_posts)
  PLATFORMS         comma list: instagram,facebook (default both)
  GRAPH_VERSION     Graph API version (default v26.0)
  MEDIA_REPO        optional public repo "owner/name" used to host the video for Instagram
  MEDIA_TOKEN       token with Contents read/write on MEDIA_REPO
  HISTORY           history file to append to (default history.json)

Instagram: resumable upload first; if Instagram refuses the file, retry with a
lighter re-encode; if that also fails and MEDIA_REPO is set, host the video for
an hour as a GitHub release asset and let Instagram fetch it (video_url).

Writes out/published.json. When at least one platform posted, appends the passage
to history.json, so a partly failed run never re-posts it to the platform that worked.
"""
import json, os, subprocess, sys, time, urllib.error, urllib.parse, urllib.request

V = os.environ.get("GRAPH_VERSION", "v26.0")
GRAPH = f"https://graph.facebook.com/{V}"
OUT = sys.argv[1] if len(sys.argv) > 1 else "out"


def call(method, url, params=None, data=None, headers=None, timeout=120):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"{method} {url.split('?')[0]} -> {e.code}: {body[:600]}")


def post_instagram(token, ig_id, video, caption, video_url=None):
    # 1. container: resumable (we upload the bytes) or video_url (Instagram fetches it)
    params = {"media_type": "REELS", "caption": caption, "share_to_feed": "true",
              "thumb_offset": "2500", "access_token": token}       # cover = frame at 2.5 s (verse on screen)
    params.update({"video_url": video_url} if video_url else {"upload_type": "resumable"})
    cid = call("POST", f"{GRAPH}/{ig_id}/media", params)["id"]
    # 2. upload the bytes
    if not video_url:
        size = os.path.getsize(video)
        with open(video, "rb") as f:
            up = call("POST", f"https://rupload.facebook.com/ig-api-upload/{V}/{cid}", data=f.read(),
                      headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size),
                               "Content-Type": "application/octet-stream"},
                      timeout=600)
        if not up.get("success", True):
            raise RuntimeError(f"Instagram upload failed: {up}")
    # 3. wait for processing
    for _ in range(60):
        st = call("GET", f"{GRAPH}/{cid}", {"fields": "status_code,status", "access_token": token})
        code = st.get("status_code")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram processing {code}: {st.get('status')}")
        time.sleep(10)
    else:
        raise RuntimeError("Instagram processing timed out")
    # 4. publish
    pub = call("POST", f"{GRAPH}/{ig_id}/media_publish", {"creation_id": cid, "access_token": token})
    media_id = pub["id"]
    link = call("GET", f"{GRAPH}/{media_id}", {"fields": "permalink", "access_token": token}).get("permalink")
    return {"id": media_id, "permalink": link}


def safe_copy(video):
    """Lighter, conservative encode (Main profile, 5 Mbps cap, 48 kHz stereo) for a second attempt."""
    dest = os.path.join(OUT, "reel_ig.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", video,
                    "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-profile:v", "main", "-level", "4.0",
                    "-maxrate", "5M", "-bufsize", "10M", "-pix_fmt", "yuv420p", "-r", "30", "-g", "60",
                    "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
                    "-movflags", "+faststart", dest], check=True)
    return dest


def gh(method, url, token, data=None, ctype="application/json"):
    body = json.dumps(data).encode() if isinstance(data, dict) else data
    return call(method, url, data=body, timeout=600,
                headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                         "Content-Type": ctype})


def host_on_github(repo, token, video):
    """Upload the video as a release asset of a public repo; returns (url, cleanup)."""
    tag = f"reel-{int(time.time())}"
    rel = gh("POST", f"https://api.github.com/repos/{repo}/releases", token,
             {"tag_name": tag, "name": tag, "body": "Temporary file for Instagram; deleted after posting."})
    def cleanup():
        for url in (f"https://api.github.com/repos/{repo}/releases/{rel['id']}",
                    f"https://api.github.com/repos/{repo}/git/refs/tags/{tag}"):
            try:
                gh("DELETE", url, token)
            except Exception as e:
                print(f"::warning title=Media cleanup failed::{str(e)[:200]}")
    try:
        with open(video, "rb") as f:
            asset = gh("POST", f"https://uploads.github.com/repos/{repo}/releases/{rel['id']}/assets?name=reel.mp4",
                       token, f.read(), "video/mp4")
    except Exception:
        cleanup()
        raise
    return asset["browser_download_url"], cleanup


def instagram(token, ig_id, video, caption):
    try:
        return post_instagram(token, ig_id, video, caption)
    except Exception as first:
        print(f"::warning title=Instagram upload refused, retrying with a lighter encode::{str(first)[:200]}")
    light = safe_copy(video)
    try:
        return post_instagram(token, ig_id, light, caption)
    except Exception as second:
        repo, gh_token = os.environ.get("MEDIA_REPO"), os.environ.get("MEDIA_TOKEN")
        if not (repo and gh_token):
            raise
        print(f"::warning title=Instagram retrying via hosted URL::{str(second)[:200]}")
    url, cleanup = host_on_github(repo, gh_token, light)
    try:
        return post_instagram(token, ig_id, light, caption, video_url=url)
    finally:
        cleanup()


def post_facebook(token, page_id, video, caption):
    s = call("POST", f"{GRAPH}/{page_id}/video_reels", {"upload_phase": "start", "access_token": token})
    vid = s["video_id"]
    size = os.path.getsize(video)
    with open(video, "rb") as f:
        call("POST", f"https://rupload.facebook.com/video-upload/{V}/{vid}", data=f.read(),
             headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size),
                      "Content-Type": "application/octet-stream"},
             timeout=600)
    call("POST", f"{GRAPH}/{page_id}/video_reels", {
        "upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
        "description": caption, "access_token": token})
    return {"id": vid, "permalink": f"https://www.facebook.com/reel/{vid}"}


def page_token_from(token, page_id):
    """Accept a Page token or a (system-)user token: if the Page hands out its own token, use it."""
    if not page_id:
        return token
    try:
        t = call("GET", f"{GRAPH}/{page_id}", {"fields": "access_token", "access_token": token}).get("access_token")
        return t or token
    except Exception:
        return token


def record(meta, results, path):
    """Append the passage to history once anything was posted (never for --surah test runs)."""
    posted = {k: v["permalink"] for k, v in results.items() if "permalink" in v}
    if not posted or meta.get("fixed"):
        return
    entry = {k: v for k, v in meta.items() if k != "fixed"}
    entry["posted"] = posted
    failed = [k for k, v in results.items() if "error" in v]
    if failed:
        entry["failed"] = failed
    history = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            history = json.load(f)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history + [entry], f, ensure_ascii=False, indent=1)


def main():
    token = os.environ.get("META_PAGE_TOKEN")
    ig_id = os.environ.get("IG_USER_ID")
    if not token or not ig_id:
        print("::warning title=Publishing skipped::META_PAGE_TOKEN / IG_USER_ID secrets are not set")
        return 0
    user_token = token                                   # system-user / user token (best for Instagram)
    token = page_token_from(token, os.environ.get("FB_PAGE_ID"))   # Page token (needed for Facebook)
    video = os.path.join(OUT, "reel.mp4")
    with open(os.path.join(OUT, "caption.txt"), encoding="utf-8") as f:
        caption = f.read().strip()[:2150]          # Instagram caption limit is 2,200 characters
    with open(os.path.join(OUT, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)
    seconds = float(meta.get("seconds", 0))

    platforms = {x.strip().lower() for x in os.environ.get("PLATFORMS", "instagram,facebook").split(",")}
    results = {}
    if "instagram" in platforms:
        try:
            results["instagram"] = instagram(user_token, ig_id, video, caption)
            print("::notice title=Posted to Instagram::" + str(results["instagram"]["permalink"]))
        except Exception as e:
            results["instagram"] = {"error": str(e)}
            print("::error title=Instagram post failed::" + str(e).replace("\n", " "))

    page_id = os.environ.get("FB_PAGE_ID")
    if page_id and "facebook" in platforms and seconds > 90:
        results["facebook"] = {"skipped": f"video is {seconds:.0f} s; Facebook Reels allow 90 s"}
        print(f"::notice title=Facebook skipped::video is {seconds:.0f} s (Facebook Reels allow 90 s)")
    elif page_id and "facebook" in platforms:
        try:
            results["facebook"] = post_facebook(token, page_id, video, caption)
            print("::notice title=Posted to Facebook::" + str(results["facebook"]["permalink"]))
        except Exception as e:
            results["facebook"] = {"error": str(e)}
            print("::error title=Facebook post failed::" + str(e).replace("\n", " "))

    with open(os.path.join(OUT, "published.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    record(meta, results, os.environ.get("HISTORY", "history.json"))
    return 1 if any("error" in r for r in results.values()) else 0    # red run -> GitHub emails you


if __name__ == "__main__":
    sys.exit(main())
