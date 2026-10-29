"""
Facebook Group Giveaway Winner Picker
=====================================
Automates picking giveaway winners from Facebook group posts (including private groups)
by connecting to your active Brave browser session where you are already logged in.

Features:
- Connects directly to Brave via Chrome DevTools Protocol (CDP) using your logged-in Facebook account.
- Automatically handles private groups (since your account is already a member).
- Automatically expands and scrolls all comments ("All comments", "View more comments").
- Strict rule validation:
    1. Only numbers within the specified range [min_number, max_number].
    2. Only 1 number per member (first valid comment counts).
    3. If two members pick the same number, the first one gets it (first come, first served).
- Cryptographically secure random winner draw using Python's `secrets` module.
- Generates exact required output:
    Picked numbers:
    [Number] - [Name]
- Fallback manual mode if you ever want to paste comments or load from a text file.
- Saves an audit log of the results (winners, stats, and disqualified entries).
"""

import sys
import os
import re
import json
import time
import socket
import secrets
from datetime import datetime
from typing import List, Dict, Optional, Tuple

CDP_PORT = 9222
CDP_URL = f"http://127.0.0.1:{CDP_PORT}"
BRAVE_DEFAULT_PATH = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"


def is_port_open(port: int = CDP_PORT, host: str = "127.0.0.1") -> bool:
    """Check if the remote debugging port is open and listening."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        return sock.connect_ex((host, port)) == 0


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
    # Find all sequences of digits
    matches = re.findall(r'\b\d+\b', text)
    valid_matches = []
    for m in matches:
        num = int(m)
        if min_num <= num <= max_num:
            valid_matches.append(num)

    # If exactly one qualifying number is found, return it
    if len(valid_matches) == 1:
        return valid_matches[0]
    
    # If multiple qualifying numbers in a single comment, return the first one
    if len(valid_matches) > 1:
        return valid_matches[0]

    return None


def fetch_comments_via_playwright(post_url: str) -> List[Dict[str, str]]:
    """
    Connects to the running Brave browser via CDP, finds or opens the post,
    expands all comments, and returns the raw comment list.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("\n[!] Playwright is not installed. Run: pip install playwright")
        return []

    print("\n Connecting to Brave browser session...")
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(CDP_URL)
        except Exception as e:
            print(f"[!] Failed to connect to Brave on {CDP_URL}: {e}")
            return []

        # Find existing tab or open a new one
        page = None
        context = browser.contexts[0] if browser.contexts else browser.new_context()

        for open_page in context.pages:
            if post_url in open_page.url or (open_page.url and "facebook.com" in open_page.url and any(part in open_page.url for part in post_url.split('/') if part and part != "https:")):
                page = open_page
                print(f"[+] Found existing Facebook tab: {page.url[:60]}...")
                break

        if page is None:
            print(f"[+] Navigating to: {post_url}")
            page = context.new_page()
            page.goto(post_url, wait_until="domcontentloaded", timeout=60000)

        page.bring_to_front()
        time.sleep(3)

        print("[+] Checking comment display settings (selecting 'All comments')...")
        try:
            # Look for comment filter dropdown (English / Filipino labels)
            filter_clicked = page.evaluate("""() => {
                const candidates = Array.from(document.querySelectorAll('div[role="button"], span[role="button"]'));
                for (const el of candidates) {
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
                # Select "All comments" / "Lahat ng komento"
                page.evaluate("""() => {
                    const items = Array.from(document.querySelectorAll('div[role="menuitem"], span, div[role="button"]'));
                    for (const el of items) {
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

        # Scroll & Collect function that runs in the browser context
        scroll_and_extract_js = """() => {
            // 1. Try clicking any expand buttons if present (View more comments, etc.)
            const clickables = Array.from(document.querySelectorAll('div[role="button"], span[role="button"], span, a'));
            for (const el of clickables) {
                if (el.offsetWidth === 0 || el.offsetHeight === 0) continue;
                const txt = (el.innerText || '').trim();
                if (!txt || txt.length > 70) continue;
                if (/(view|tingnan|see)\\s+(all|\\d+\\s+)?(previous|more|nakaraan|higit).*comment/i.test(txt) ||
                    /(view|tingnan|see)\\s+(all|\\d+\\s+)?(previous|more|nakaraan|higit).*komento/i.test(txt) ||
                    /^\\d+\\s+(previous|more|nakaraan|higit)\\s+(comment|komento)/i.test(txt)) {
                    el.scrollIntoView({ behavior: 'auto', block: 'center' });
                    el.click();
                    break;
                }
            }

            // 2. Find the scrollable container that holds the comments
            const allDivs = Array.from(document.querySelectorAll('div'));
            const scrollable = allDivs.find(el => {
                const s = window.getComputedStyle(el);
                return (s.overflowY === 'auto' || s.overflowY === 'scroll') &&
                       el.querySelectorAll('div[role="article"]').length > 0;
            });

            // 3. Scroll to bottom of container to trigger Facebook's infinite scroll loader
            let containerRect = null;
            if (scrollable) {
                scrollable.scrollTop = scrollable.scrollHeight;
                scrollable.dispatchEvent(new Event('scroll', { bubbles: true }));
                const r = scrollable.getBoundingClientRect();
                containerRect = { x: r.x + r.width / 2, y: r.y + r.height / 2 };
            } else {
                // Fallback to window scroll
                window.scrollTo(0, document.body.scrollHeight);
            }

            // 4. Extract all currently visible comments (handles virtualization)
            const articles = Array.from(document.querySelectorAll('div[role="article"]'));
            const extracted = [];
            articles.forEach(node => {
                const authorEl = node.querySelector('a[role="link"] span, h3 span, span > strong');
                const author = authorEl ? authorEl.innerText.trim() : null;
                const textEl = node.querySelector('div[dir="auto"]');
                const text = textEl ? textEl.innerText.trim() : '';
                if (author && text) {
                    extracted.push({ name: author, text: text });
                }
            });

            return {
                containerFound: !!scrollable,
                containerRect,
                visibleCount: articles.length,
                comments: extracted
            };
        }"""

        accumulated_comments = {}  # (author, text) -> dict
        consecutive_stagnant = 0
        max_scroll_passes = 300  # Automatically stops when end of comments is reached

        for pass_num in range(1, max_scroll_passes + 1):
            data = page.evaluate(scroll_and_extract_js)
            
            # Dispatch mouse wheel directly over the container's center coordinates
            rect = data.get("containerRect")
            if rect:
                page.mouse.move(rect["x"], rect["y"])
                page.mouse.wheel(0, 1800)
            else:
                page.mouse.wheel(0, 1800)

            # Accumulate new comments
            before_count = len(accumulated_comments)
            for c in data.get("comments", []):
                key = (c["name"], c["text"])
                if key not in accumulated_comments:
                    accumulated_comments[key] = c

            total_now = len(accumulated_comments)
            visible_dom = data.get("visibleCount", 0)

            # Print live progress
            if pass_num % 2 == 0 or total_now != before_count:
                print(f"    [+] Scroll Pass {pass_num}: {total_now} unique comments accumulated ({visible_dom} currently in view)...")

            if total_now == before_count:
                consecutive_stagnant += 1
                # Wait slightly longer to let Facebook GraphQL response arrive
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
    claimed_numbers = {}  # number -> member_name
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

        # Rule: If number is the same from another, pick the first member who commented that number
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
    
    # Secure shuffle using SystemRandom
    rng = secrets.SystemRandom()
    shuffled = list(valid_entries)
    rng.shuffle(shuffled)
    
    winners_count = min(count, len(shuffled))
    return shuffled[:winners_count]


def print_instructions_for_brave_debugging():
    """Prints clear instructions on how to start Brave with remote debugging enabled."""
    print("\n" + "="*70)
    print(" [!] BRAVE REMOTE DEBUGGING IS NOT ACTIVE")
    print("="*70)
    print("To allow the script to read from your private Facebook group, Brave")
    print("must be launched with the remote debugging port enabled (port 9222).\n")
    print("HOW TO START BRAVE IN DEBUG MODE:")
    print("1. Close all currently open Brave windows.")
    print("2. Run the included helper script:")
    print(r"   start_brave_with_debugging.bat")
    print("   OR run this command in terminal:")
    print(rf'   "{BRAVE_DEFAULT_PATH}" --remote-debugging-port={CDP_PORT}')
    print("3. Log into Facebook if not already logged in, then rerun this script.")
    print("="*70 + "\n")


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
    
    # Try line format: "Name: 123" or "Name - 123"
    for line in lines:
        if ":" in line:
            parts = line.split(":", 1)
            raw.append({"name": parts[0].strip(), "text": parts[1].strip()})
        elif " - " in line:
            parts = line.split(" - ", 1)
            raw.append({"name": parts[0].strip(), "text": parts[1].strip()})
        else:
            # Generic fallback
            raw.append({"name": "Participant", "text": line})
    return raw


def main():
    print("=" * 60)
    print("      FACEBOOK GIVEAWAY WINNER PICKER (PRIVATE GROUPS)")
    print("=" * 60)

    # 1. Inputs
    post_url = prompt_validated_url("Enter Facebook giveaway link: ")
    min_num = prompt_validated_int("Enter minimum number (e.g. 1): ", min_val=0)
    max_num = prompt_validated_int(f"Enter maximum number (must be > {min_num}): ", min_val=min_num + 1)
    num_winners = prompt_validated_int("Enter how many winners: ", min_val=1)

    print("\n--- Summary of Giveaway Configuration ---")
    print(f" Post URL:      {post_url}")
    print(f" Number Range:  [{min_num} to {max_num}]")
    print(f" Rules:         1 number/member; first commenter wins duplicate numbers")
    print(f" Target Winners: {num_winners}")
    print("-" * 60)

    # 2. Check if Brave CDP port is open
    raw_comments = []
    if is_port_open(CDP_PORT):
        print(f"[+] Brave remote debugging detected on port {CDP_PORT}!")
        raw_comments = fetch_comments_via_playwright(post_url)
    else:
        print_instructions_for_brave_debugging()
        choice = input("Would you like to (1) Retry after starting Brave, or (2) Paste comments manually? [1/2]: ").strip()
        if choice == "2":
            raw_comments = manual_paste_mode(min_num, max_num)
        else:
            input("Press Enter once you have started Brave with remote debugging...")
            if is_port_open(CDP_PORT):
                raw_comments = fetch_comments_via_playwright(post_url)
            else:
                print("[!] Port 9222 is still not responding. Switching to manual paste mode.")
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

    # Check if requested winners exceeds valid pool
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
        f.write("FACEBOOK GIVEAWAY WINNER AUDIT REPORT\n")
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


if __name__ == "__main__":
    main()
