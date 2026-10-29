"""
Facebook Group Giveaway Winner Picker
=====================================
Automates picking giveaway winners from Facebook group posts (including private groups)
by connecting to your active browser session (Brave, Chrome, Edge, etc.) where you are already logged in.

Features:
- Multi-browser support: Brave Browser, Google Chrome, Microsoft Edge, and Mozilla Firefox.
- 1-Step automated launcher: Checks for active debug port and can automatically launch or restart
  your browser with remote debugging enabled.
- Automatically handles private groups (since your account is already a member).
- Infinite-scroll modal loader with live comment accumulation (prevents virtualization data loss).
- Strict rule validation:
    1. Only numbers within the specified range [min_number, max_number].
    2. Only 1 number per member (first valid comment counts).
    3. If two members pick the same number, the first one gets it (first come, first served).
- Cryptographically secure random winner draw using Python's `secrets` module.
- Generates clean announcement output without prohibited words.
- Saves an audit log of the results (winners, stats, and disqualified entries) to `results/`.
"""

import sys
import os
import re
import json
import time
import socket
import secrets
import subprocess
from datetime import datetime
from typing import List, Dict, Optional, Tuple

CDP_PORT = 9222
CDP_URL = f"http://127.0.0.1:{CDP_PORT}"

SUPPORTED_BROWSERS = {
    "brave": {
        "name": "Brave Browser",
        "process_name": "brave.exe",
        "paths": [
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        ],
    },
    "chrome": {
        "name": "Google Chrome",
        "process_name": "chrome.exe",
        "paths": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ],
    },
    "edge": {
        "name": "Microsoft Edge",
        "process_name": "msedge.exe",
        "paths": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
        ],
    },
    "firefox": {
        "name": "Mozilla Firefox",
        "process_name": "firefox.exe",
        "paths": [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
        ],
    },
}


def is_port_open(port: int = CDP_PORT, host: str = "127.0.0.1") -> bool:
    """Check if the remote debugging port is open and listening."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        return sock.connect_ex((host, port)) == 0


def get_installed_browsers() -> Dict[str, Dict]:
    """Scans the system for installed supported browsers."""
    installed = {}
    for key, info in SUPPORTED_BROWSERS.items():
        for path in info["paths"]:
            if os.path.exists(path):
                installed[key] = {**info, "path": path}
                break
    return installed


def is_process_running(process_name: str) -> bool:
    """Check if a specific process is currently running on Windows."""
    try:
        output = subprocess.check_output(
            ["tasklist", "/FI", f"IMAGENAME eq {process_name}"],
            text=True,
            stderr=subprocess.DEVNULL
        )
        return process_name.lower() in output.lower()
    except Exception:
        return False


def graceful_close_browser(process_name: str, timeout: float = 3.5):
    """
    Gracefully asks the browser windows to close so all tabs and session state are preserved.
    Avoids abrupt termination which triggers the 'Brave didn't shut down correctly' crash prompt.
    """
    # 1. Send graceful WM_CLOSE via taskkill (without /F)
    try:
        subprocess.run(
            ["taskkill", "/IM", process_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass

    # Wait for the browser process to write session files and exit cleanly
    start = time.time()
    while time.time() - start < timeout:
        if not is_process_running(process_name):
            return True
        time.sleep(0.4)

    # 2. If background helper processes linger after timeout, clean them up
    try:
        subprocess.run(
            ["taskkill", "/IM", process_name, "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(1.0)
    except Exception:
        pass
    return True


def clean_browser_exit_state(browser_key: str):
    """Ensures the browser profile preferences don't trigger the 'crashed' dialog."""
    pref_paths = {
        "brave": os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\User Data\Default\Preferences"),
        "chrome": os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Preferences"),
        "edge": os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Preferences"),
    }
    pref_file = pref_paths.get(browser_key)
    if pref_file and os.path.exists(pref_file):
        try:
            with open(pref_file, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
            modified = False
            if "profile" in data:
                if data["profile"].get("exit_type") != "Normal":
                    data["profile"]["exit_type"] = "Normal"
                    modified = True
                if data["profile"].get("exited_cleanly") is False:
                    data["profile"]["exited_cleanly"] = True
                    modified = True
            if modified:
                with open(pref_file, "w", encoding="utf-8") as f:
                    json.dump(data, f)
        except Exception:
            pass


def launch_browser_with_debugging(browser_path: str, port: int = CDP_PORT) -> bool:
    """
    Launches the browser with remote debugging enabled, automatically restoring
    all previously open tabs without showing the crash prompt.
    """
    cmd = [
        browser_path,
        f"--remote-debugging-port={port}",
        "--restore-last-session",
        "--disable-session-crashed-bubble",
    ]
    try:
        subprocess.Popen(cmd)
        print(f"[+] Re-opening browser on port {port} (restoring all tabs)...")
        # Wait up to 10 seconds for the port to start responding
        for _ in range(20):
            time.sleep(0.5)
            if is_port_open(port):
                return True
        return False
    except Exception as e:
        print(f"[!] Error launching browser: {e}")
        return False


def ensure_browser_session() -> bool:
    """
    Ensures that a browser is active and listening on the CDP debugging port.
    If not open, offers to launch or restart the chosen browser automatically.
    """
    if is_port_open(CDP_PORT):
        print(f"[+] Active browser session detected on debug port {CDP_PORT}!")
        return True

    installed = get_installed_browsers()
    if not installed:
        print("[!] Could not auto-detect any supported browsers (Brave, Chrome, Edge, Firefox).")
        return False

    print("\n" + "=" * 60)
    print("        BROWSER SELECTION & AUTO-CONNECT")
    print("=" * 60)
    print("Which browser are you logged into Facebook on?")
    
    browser_keys = list(installed.keys())
    for idx, key in enumerate(browser_keys, 1):
        info = installed[key]
        tag = " (Recommended)" if key == "brave" else ""
        print(f"  [{idx}] {info['name']}{tag}")

    choice_str = input(f"Enter choice [1-{len(browser_keys)}] (Default 1): ").strip()
    try:
        choice_idx = int(choice_str) - 1
        if 0 <= choice_idx < len(browser_keys):
            selected_key = browser_keys[choice_idx]
        else:
            selected_key = browser_keys[0]
    except ValueError:
        selected_key = browser_keys[0]

    chosen = installed[selected_key]
    print(f"\n[+] Selected: {chosen['name']}")

    # Check if this browser is already running without debugging
    if is_process_running(chosen["process_name"]):
        print(f"\n[*] {chosen['name']} is currently running without remote debugging.")
        print("    To access private Facebook groups, it must be restarted with debugging enabled.")
        restart_choice = input(f"    Restart {chosen['name']} now? (all tabs will be restored) (Y/n) [Y]: ").strip().lower()
        if restart_choice != 'n':
            print(f"[+] Gracefully closing {chosen['name']} to save open tabs...")
            graceful_close_browser(chosen["process_name"])
            clean_browser_exit_state(selected_key)
            return launch_browser_with_debugging(chosen["path"], CDP_PORT)
        else:
            print("[!] Cannot connect to running browser without debug port.")
            return False
    else:
        # Browser is not running, just launch it directly
        clean_browser_exit_state(selected_key)
        return launch_browser_with_debugging(chosen["path"], CDP_PORT)


def prompt_validated_int(prompt_text: str, min_val: Optional[int] = None, max_val: Optional[int] = None) -> int:
    """Prompt user for an integer with bounds validation."""
    while True:
        user_input = input(prompt_text).strip()
        try:
            val = int(user_input)
            if min_val is not None and val < min_val:
                print(f"  [!] Must be at least {min_val}. Try again.")
                continue
            if max_val is not None and val > max_val:
                print(f"  [!] Must be at most {max_val}. Try again.")
                continue
            return val
        except ValueError:
            print("  [!] Invalid number. Please enter a whole integer.")


def prompt_validated_url(prompt_text: str) -> str:
    """Prompt user for a valid Facebook link."""
    while True:
        url = input(prompt_text).strip()
        if not url:
            print("  [!] URL cannot be empty. Try again.")
            continue
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
        if "facebook.com" not in url:
            print("  [!] Please enter a valid Facebook URL (e.g. https://www.facebook.com/groups/.../posts/...).")
            continue
        return url


def extract_number_from_text(text: str, min_num: int, max_num: int) -> Optional[int]:
    """
    Extracts a qualifying integer from comment text within [min_num, max_num].
    Handles patterns like: "42", "#42", "My number is 42", "42.", etc.
    """
    matches = re.findall(r'\b\d+\b', text)
    valid_matches = []
    for m in matches:
        num = int(m)
        if min_num <= num <= max_num:
            valid_matches.append(num)

    if len(valid_matches) >= 1:
        return valid_matches[0]

    return None


def fetch_comments_via_playwright(post_url: str) -> List[Dict[str, str]]:
    """
    Connects to the browser via CDP, navigates to the post,
    scrolls and expands the comments, and accumulates entries live.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("\n[!] Playwright is not installed. Run: pip install playwright")
        return []

    print("\n Connecting to browser session via CDP...")
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(CDP_URL)
        except Exception as e:
            print(f"[!] Failed to connect on {CDP_URL}: {e}")
            return []

        # Extract specific post identifier (e.g. numeric ID "1557723966073416")
        post_id_matches = re.findall(r"\d{10,}", post_url)
        target_id = post_id_matches[-1] if post_id_matches else post_url.rstrip("/")

        page = None
        context = browser.contexts[0] if browser.contexts else browser.new_context()

        for open_page in context.pages:
            if target_id in open_page.url or (open_page.url and post_url.rstrip("/").lower() in open_page.url.lower()):
                page = open_page
                print(f"[+] Found existing target post tab: {page.url[:60]}...")
                break

        if page is None:
            print(f"[+] Opening target post in new tab: {post_url}")
            page = context.new_page()
            page.goto(post_url, wait_until="domcontentloaded", timeout=60000)
        else:
            # If the found tab is on a different page, navigate to the target post
            if target_id not in page.url:
                print(f"[+] Navigating tab to target post: {post_url}")
                page.goto(post_url, wait_until="domcontentloaded", timeout=60000)

        page.bring_to_front()
        time.sleep(3)

        print("[+] Checking comment display settings (selecting 'All comments')...")
        try:
            filter_clicked = page.evaluate("""() => {
                const candidates = Array.from(document.querySelectorAll('div[role="button"], span[role="button"]'));
                for (const el of candidates) {
                    if (el.tagName === 'A' || el.closest('a')) continue;
                    const txt = (el.innerText || '').trim().toLowerCase();
                    if (txt === 'most relevant' || txt === 'top comments' || txt === 'pinakanauugnay') {
                        el.click();
                        return true;
                    }
                }
                return false;
            }""")
            if filter_clicked:
                time.sleep(1.5)
                page.evaluate("""() => {
                    const items = Array.from(document.querySelectorAll('div[role="menuitem"], span, div[role="button"]'));
                    for (const el of items) {
                        if (el.tagName === 'A' || el.closest('a')) continue;
                        const txt = (el.innerText || '').trim().toLowerCase();
                        if (txt.includes('all comments') || txt.includes('lahat ng komento')) {
                            el.click();
                            return true;
                        }
                    }
                    return false;
                }""")
                print("[+] Successfully switched comment filter to 'All comments'.")
                time.sleep(3)
            else:
                print("[+] Comment filter is already on 'All comments' or default.")
        except Exception as e:
            print(f"[-] Filter check note: {e}")

        print("[+] Scrolling and loading comments (this will continuously scroll until all comments are loaded)...")

        # Scroll & Collect function strictly scoped to the target post container
        scroll_and_extract_js = """() => {
            // 1. Locate the scrollable container that contains the target comments
            const all = Array.from(document.querySelectorAll('div'));
            const scrollable = all.find(el => {
                const s = window.getComputedStyle(el);
                return (s.overflowY === 'auto' || s.overflowY === 'scroll') &&
                       el.querySelectorAll('div[role="article"]').length > 0;
            });

            // 2. Scroll to bottom of container to trigger Facebook's infinite scroll loader
            let containerRect = null;
            if (scrollable) {
                scrollable.scrollTop = scrollable.scrollHeight;
                scrollable.dispatchEvent(new Event('scroll', { bubbles: true }));
                const r = scrollable.getBoundingClientRect();
                containerRect = { x: r.x + r.width / 2, y: r.y + r.height / 2 };
            } else {
                window.scrollTo(0, document.body.scrollHeight);
            }

            // 3. Extract all currently visible comments
            const articles = Array.from(document.querySelectorAll('div[role="article"]'));
            const extracted = [];
            for (const a of articles) {
                const raw = a.innerText || '';
                const lines = raw.split(/\\r?\\n/).map(l => l.trim()).filter(Boolean);
                if (lines.length < 2) continue;

                const author = lines[0];
                if (author.includes('status indicator') || author.length < 2) continue;

                let text = '';
                for (let i = 1; i < lines.length; i++) {
                    const l = lines[i];
                    if (/^\\d+\\s*[smhdwy]$|^like$|^reply$|^edited$/i.test(l)) continue;
                    text = l;
                    break;
                }
                if (author && text) {
                    extracted.push({ name: author, text: text });
                }
            }

            return {
                containerFound: !!scrollable,
                containerRect,
                visibleCount: articles.length,
                comments: extracted
            };
        }"""

        accumulated_comments = {}
        consecutive_stagnant = 0
        max_scroll_passes = 300  # Automatically stops when end of comments is reached

        for pass_num in range(1, max_scroll_passes + 1):
            data = page.evaluate(scroll_and_extract_js)
            
            rect = data.get("containerRect")
            if rect:
                page.mouse.move(rect["x"], rect["y"])
                page.mouse.wheel(0, 1800)
            else:
                page.mouse.wheel(0, 1800)

            before_count = len(accumulated_comments)
            for c in data.get("comments", []):
                key = (c["name"], c["text"])
                if key not in accumulated_comments:
                    accumulated_comments[key] = c

            total_now = len(accumulated_comments)
            visible_dom = data.get("visibleCount", 0)

            if pass_num % 2 == 0 or total_now != before_count:
                print(f"    [+] Scroll Pass {pass_num}: {total_now} unique comments accumulated ({visible_dom} currently in view)...")

            if total_now == before_count:
                consecutive_stagnant += 1
                time.sleep(2.0)
                if consecutive_stagnant >= 6:
                    print(f"[+] Reached end of comments! No new comments loaded after {consecutive_stagnant} scroll checks.")
                    break
            else:
                consecutive_stagnant = 0
                time.sleep(1.6)

        raw_comments = list(accumulated_comments.values())
        print(f"\n[+] Total unique comments collected: {len(raw_comments)}")
        return raw_comments


def process_entries(
    raw_comments: List[Dict[str, str]],
    min_num: int,
    max_num: int
) -> Tuple[List[Dict], List[Dict]]:
    """
    Applies the giveaway rules:
    1. Must have a number between min_num and max_num.
    2. 1 number per member only (first comment by member is used).
    3. Duplicate number: First member who commented that number gets it.

    Returns:
        (valid_entries, disqualified_entries)
    """
    seen_members = set()
    claimed_numbers = {}
    valid_entries = []
    disqualified = []

    for item in raw_comments:
        name = item.get("name", "").strip()
        text = item.get("text", "").strip()

        # Check for qualifying number
        num = extract_number_from_text(text, min_num, max_num)
        if num is None:
            disqualified.append({
                "name": name,
                "text": text,
                "reason": f"No valid number between {min_num} and {max_num}"
            })
            continue

        # Rule: 1 number per member only
        if name in seen_members:
            disqualified.append({
                "name": name,
                "number": num,
                "text": text,
                "reason": f"Multiple entries by member (Already entered previously)"
            })
            continue
        seen_members.add(name)

        # Rule: First member who commented that number gets it
        if num in claimed_numbers:
            first_claimant = claimed_numbers[num]
            disqualified.append({
                "name": name,
                "number": num,
                "text": text,
                "reason": f"Number {num} already claimed earlier by {first_claimant}"
            })
            continue

        claimed_numbers[num] = name
        valid_entries.append({
            "number": num,
            "name": name,
            "text": text
        })

    return valid_entries, disqualified


def draw_winners(valid_entries: List[Dict], count: int) -> List[Dict]:
    """Cryptographically secure, fair selection of winners."""
    if not valid_entries:
        return []
    
    rng = secrets.SystemRandom()
    shuffled = list(valid_entries)
    rng.shuffle(shuffled)
    
    winners_count = min(count, len(shuffled))
    return shuffled[:winners_count]


def manual_paste_mode(min_num: int, max_num: int) -> List[Dict[str, str]]:
    """Fallback mode: allows user to paste comments text or load from a file."""
    print("\n--- Fallback Mode: Paste Comments ---")
    print("You can paste the comment text here, or save it to 'comments.txt'.")
    print("Format expected: [Author Name] followed by their comment or number,")
    print("OR simple lines like: John Doe: 145")
    
    file_path = "comments.txt"
    if os.path.exists(file_path):
        use_file = input(f"Found '{file_path}'. Load comments from this file? (Y/n): ").strip().lower()
        if use_file != 'n':
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return parse_pasted_text(content)

    print("\nPaste your comments below (Press Ctrl+Z then Enter on Windows to finish):")
    lines = sys.stdin.read()
    return parse_pasted_text(lines)


def parse_pasted_text(content: str) -> List[Dict[str, str]]:
    """Parses raw pasted text into name and comment text."""
    raw = []
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    
    for line in lines:
        if ":" in line:
            parts = line.split(":", 1)
            raw.append({"name": parts[0].strip(), "text": parts[1].strip()})
        elif " - " in line:
            parts = line.split(" - ", 1)
            raw.append({"name": parts[0].strip(), "text": parts[1].strip()})
        else:
            raw.append({"name": "Participant", "text": line})
    return raw


def main():
    print("=" * 65)
    print("          FACEBOOK GROUP WINNER PICKER (PRIVATE GROUPS)")
    print("          Developed by Nomer Israel (https://github.com/nmrisrl11)")
    print("=" * 65)

    # 1. Inputs
    post_url = prompt_validated_url("Enter Facebook post link: ")
    min_num = prompt_validated_int("Enter minimum number (e.g. 1): ", min_val=0)
    max_num = prompt_validated_int(f"Enter maximum number (must be > {min_num}): ", min_val=min_num + 1)
    num_winners = prompt_validated_int("Enter how many winners: ", min_val=1)

    print("\n--- Summary of Configuration ---")
    print(f" Post URL:      {post_url}")
    print(f" Number Range:  [{min_num} to {max_num}]")
    print(f" Rules:         1 number/member; first commenter wins duplicate numbers")
    print(f" Target Winners: {num_winners}")
    print("-" * 60)

    # 2. Automated browser session check and launch
    raw_comments = []
    if ensure_browser_session():
        raw_comments = fetch_comments_via_playwright(post_url)
    else:
        choice = input("Would you like to (1) Retry connecting, or (2) Paste comments manually? [1/2]: ").strip()
        if choice == "2":
            raw_comments = manual_paste_mode(min_num, max_num)
        else:
            if ensure_browser_session():
                raw_comments = fetch_comments_via_playwright(post_url)
            else:
                print("[!] Unable to attach to browser. Switching to manual paste mode.")
                raw_comments = manual_paste_mode(min_num, max_num)

    if not raw_comments:
        print("\n[!] No comments retrieved. Please check the post URL or ensure comments are visible.")
        return

    print(f"\n[+] Total raw comments collected: {len(raw_comments)}")

    # 3. Apply Rules and Process Entries
    valid_entries, disqualified = process_entries(raw_comments, min_num, max_num)

    print(f"[+] Valid unique qualifying entries: {len(valid_entries)}")
    print(f"[-] Disqualified comments:           {len(disqualified)}")

    if not valid_entries:
        print("\n[!] No valid entries found matching the criteria!")
        if disqualified:
            print("\nSample disqualified reasons:")
            for d in disqualified[:5]:
                print(f"  - {d.get('name')}: {d.get('reason')} ('{d.get('text')}')")
        return

    if num_winners > len(valid_entries):
        print(f"\n[!] Note: You requested {num_winners} winners, but only {len(valid_entries)} valid entries qualify.")
        print(f"    Selecting all {len(valid_entries)} qualifying participants as winners.")

    # 4. Draw Winners
    winners = draw_winners(valid_entries, num_winners)

    # 5. Output in exact requested format with congratulations & thank you
    output_lines = ["\nPicked numbers:\n"]
    for w in winners:
        output_lines.append(f"{w['number']} - {w['name']}")
    
    output_lines.append("")
    output_lines.append("🎉 Congratulations to all the winners!")
    output_lines.append("🙏 Thank you so much to everyone who participated! Stay tuned for the next one!")
    
    output_str = "\n".join(output_lines)

    print("\n" + "=" * 55)
    print(output_str)
    print("=" * 55 + "\n")

    # 6. Save Audit Report in results folder
    results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    os.makedirs(results_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = f"giveaway_result_{timestamp}.txt"
    report_path = os.path.join(results_dir, report_filename)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("WINNER AUDIT REPORT\n")
        f.write("=" * 55 + "\n")
        f.write(f"Date:           {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Post URL:       {post_url}\n")
        f.write(f"Number Range:   {min_num} - {max_num}\n")
        f.write(f"Total Comments: {len(raw_comments)}\n")
        f.write(f"Valid Entries:  {len(valid_entries)}\n")
        f.write(f"Disqualified:   {len(disqualified)}\n")
        f.write("\n" + output_str + "\n\n")
        
        f.write("ALL QUALIFYING ENTRIES:\n")
        f.write("-" * 55 + "\n")
        for e in valid_entries:
            f.write(f"  {e['number']} - {e['name']}\n")

        if disqualified:
            f.write("\nDISQUALIFIED ENTRIES:\n")
            f.write("-" * 55 + "\n")
            for d in disqualified:
                f.write(f"  {d.get('name')}: {d.get('reason')} [Comment: '{d.get('text')}']\n")

    print(f"[+] Full audit report saved to: results/{report_filename}")
    print("\n" + "-" * 55)
    print("👤 Developer: Nomer Israel (https://github.com/nmrisrl11)")
    print("☕ Buy me a coffee: https://buymeacoffee.com/nmrisrl11")
    print("-" * 55)


if __name__ == "__main__":
    main()
