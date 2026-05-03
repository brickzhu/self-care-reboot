#!/usr/bin/env python3
"""
Gomoku polling notification for mode "every step AI think"
- Polls for game state
- When it's my turn, send webhook to OpenClaw session to wake up AI
- Also sends direct message to wechat to ensure user receives notification
- Fully automatic: detects -> wakes up AI -> AI thinks -> makes move -> continues polling
"""

import sys
import time
import requests
import json
import os
import subprocess
from typing import List, Tuple, Dict, Optional

# OpenClaw webhook configuration
OPENCLAW_HOOK_URL = "http://127.0.0.1:18789/hooks/wake"
OPENCLAW_HOOK_TOKEN = "c5137eee0074daed0b53c1b8f9181f0bb6722354999fb3ea"
# Wechat target (your channel user id)
WECHAT_TARGET = "o9cq803tDvug9NtD06KoBNCmP9_g@im.weixin"

def send_webhook_notification(text: str):
    """Send webhook notification to OpenClaw to wake up AI session"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENCLAW_HOOK_TOKEN}"
    }
    body = {
        "text": text
    }
    try:
        resp = requests.post(OPENCLAW_HOOK_URL, headers=headers, json=body, timeout=10)
        if resp.status_code == 200:
            print(f"[OK] Webhook notification sent to wake AI: {text[:50]}...")
        else:
            print(f"[WARN] Webhook returned {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"[ERROR] Failed to send webhook: {e}")

def send_wechat_notification(text: str):
    """Send notification directly to wechat user via message tool"""
    cmd = [
        "openclaw", "message", "send",
        "--channel", "openclaw-weixin",
        "--to", WECHAT_TARGET,
        "--message", text
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            print(f"[OK] Wechat notification sent: {text[:50]}...")
        else:
            print(f"[WARN] Wechat notification failed: {result.stderr}")
    except Exception as e:
        print(f"[ERROR] Failed to send wechat notification: {e}")

def send_turn_notification(match_id: str, move_count: int):
    """Send notification when it's my turn"""
    message = f"🚨 轮到我走了！棋局 {match_id}，第 {move_count} 步，请 AI 思考落子"
    send_webhook_notification(message)
    send_wechat_notification(message)

def send_move_done_notification(match_id: str, move_count: int):
    """Send notification when AI has finished moving"""
    message = f"✅ 我已经落完子了！棋局 {match_id}，第 {move_count} 步完成，等待对手下一步。"
    send_wechat_notification(message)

def send_game_over_notification(match_id: str, winner: str, reason: str):
    """Send notification when game is finished"""
    message = f"🏁 棋局结束！{match_id}，获胜者：{winner}，原因：{reason}"
    send_webhook_notification(message)
    send_wechat_notification(message)

def poll_and_notify(api_base: str, match_id: str, user_id: str, interval: float = 2):
    """Main polling loop that sends webhook when it's my turn"""
    
    print(f"[START] Starting automatic polling with webhook for match {match_id}")
    print(f"[INFO] User ID: {user_id}")
    print(f"[INFO] API base: {api_base}")
    print(f"[INFO] Poll interval: {interval}s")
    print(f"[INFO] Mode: Automatic webhook notification when it's my turn")
    print(f"[INFO] Hook URL: {OPENCLAW_HOOK_URL}")
    
    # api_base is http://domain:port, need to add /api/v1
    if not api_base.endswith("/api/v1"):
        api_base = f"{api_base.rstrip('/')}/api/v1"
    url = f"{api_base}/matches/{match_id}"
    headers = {"X-User-Id": user_id}
    
    last_move_count = -1
    
    while True:
        try:
            resp = requests.get(url, headers=headers, params={"forAgent": 1}, timeout=15)
            data = resp.json()
            
            if not data.get("ok"):
                print(f"[ERROR] {data.get('error', {}).get('message', 'Unknown error')}")
                time.sleep(interval)
                continue
            
            item = data["item"]
            status = item.get("status")
            move_count = len(item.get("moveHistory", []))
            
            if status == "finished":
                winner = item.get("winnerUserId")
                reason = item.get("winReason", "")
                print(f"\n[INFO] Game finished. Winner: {winner}, reason: {reason}")
                # Send game over notification
                send_game_over_notification(match_id, winner, reason)
                break
            
            ai_input = item.get("agentInput", {})
            if not ai_input.get("isYourTurn"):
                if move_count != last_move_count:
                    print(f"[INFO] Move count: {move_count}, waiting...")
                    last_move_count = move_count
                time.sleep(interval)
                continue
            
            # It's my turn! Send webhook notification
            print("\n" + "="*60)
            print("🚨 IT'S MY TURN! Sending webhook notification...")
            print(f"   Match ID: {match_id}")
            print(f"   Move count: {move_count}")
            print(f"   My stone: {ai_input.get('yourStone')}")
            print("="*60 + "\n")
            send_turn_notification(match_id, move_count)
            # Keep polling after notification, wait for next round after AI moves
            last_move_count = move_count
            # Wait longer after notification, since AI needs time to think and move
            time.sleep(interval * 10)
            continue
            
        except Exception as e:
            print(f"[ERROR] Exception: {e}")
            time.sleep(interval)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Gomoku AI polling notification (no auto-play)")
    parser.add_argument("--match-id", required=True, help="Match ID")
    parser.add_argument("--user-id", required=True, help="My user ID (X-User-Id)")
    parser.add_argument("--api-url", default="http://43.160.197.143:19100", help="API base URL")
    parser.add_argument("--interval", type=float, default=1.5, help="Poll interval in seconds")
    args = parser.parse_args()
    
    poll_and_notify(args.api_url, args.match_id, args.user_id, args.interval)

if __name__ == "__main__":
    main()
