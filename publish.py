#!/usr/bin/env python3
"""
Publish out/reel.mp4 with out/caption.txt to Instagram Reels (and, when allowed, the Facebook Page).

Environment (GitHub secrets):
  META_PAGE_TOKEN   Page access token (from a long-lived user token -> does not expire)
  IG_USER_ID        Instagram professional account id (instagram_business_account.id)
  FB_PAGE_ID        Facebook Page id (optional; Facebook posting needs pages_manage_posts)
  POST_TO_FACEBOOK  "true" to also post to the Page (default: false)
  GRAPH_VERSION     Graph API version (default v26.0)

Uses Meta's resumable upload, so the video is sent straight from the runner;
no public hosting is needed. Writes out/published.json with the results.
"""
import json, os, sys, time, urllib.error, urllib.parse, urllib.request

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


def post_instagram(token, ig_id, video, caption):
    # 1. resumable container
    c = call("POST", f"{GRAPH}/{ig_id}/media", {
        "media_type": "REELS", "upload_type": "resumable", "caption": caption,
        "share_to_feed": "true", "access_token": token})
    cid = c["id"]
    # 2. upload the bytes
    size = os.path.getsize(video)
    with open(video, "rb") as f:
        up = call("POST", f"https://rupload.facebook.com/ig-api-upload/{V}/{cid}", data=f.read(),
                  headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size)},
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


def post_facebook(token, page_id, video, caption):
    s = call("POST", f"{GRAPH}/{page_id}/video_reels", {"upload_phase": "start", "access_token": token})
    vid = s["video_id"]
    size = os.path.getsize(video)
    with open(video, "rb") as f:
        call("POST", f"https://rupload.facebook.com/video-upload/{V}/{vid}", data=f.read(),
             headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size)},
             timeout=600)
    call("POST", f"{GRAPH}/{page_id}/video_reels", {
        "upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
        "description": caption, "access_token": token})
    return {"id": vid, "permalink": f"https://www.facebook.com/reel/{vid}"}


def main():
    token = os.environ.get("META_PAGE_TOKEN")
    ig_id = os.environ.get("IG_USER_ID")
    if not token or not ig_id:
        print("Publishing skipped: META_PAGE_TOKEN / IG_USER_ID secrets are not set yet.")
        return 0
    video = os.path.join(OUT, "reel.mp4")
    with open(os.path.join(OUT, "caption.txt"), encoding="utf-8") as f:
        caption = f.read().strip()[:2150]          # Instagram caption limit is 2,200 characters

    results, failed = {}, False
    try:
        results["instagram"] = post_instagram(token, ig_id, video, caption)
        print("Instagram:", results["instagram"]["permalink"])
    except Exception as e:
        failed = True
        results["instagram"] = {"error": str(e)}
        print("::error title=Instagram post failed::" + str(e).replace("\n", " "))

    page_id = os.environ.get("FB_PAGE_ID")
    if page_id and os.environ.get("POST_TO_FACEBOOK", "false").lower() == "true":
        try:
            results["facebook"] = post_facebook(token, page_id, video, caption)
            print("Facebook:", results["facebook"]["permalink"])
        except Exception as e:
            results["facebook"] = {"error": str(e)}          # Facebook failure doesn't fail the run
            print("::warning title=Facebook post failed::" + str(e).replace("\n", " "))

    with open(os.path.join(OUT, "published.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
