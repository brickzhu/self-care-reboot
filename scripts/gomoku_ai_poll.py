#!/usr/bin/env python3
"""
Gomoku automatic AI polling player
Heuristic: block opponent first, then build own connections
"""

import sys
import time
import requests
import json
from typing import List, Tuple, Dict, Optional

BOARD_SIZE = 15

class GomokuAI:
    def __init__(self):
        # Directions: horizontal, vertical, two diagonals
        self.directions = [
            [(0, 1), (0, -1)],   # vertical
            [(1, 0), (-1, 0)],   # horizontal
            [(1, 1), (-1, -1)],  # diagonal down-right
            [(1, -1), (-1, 1)],  # diagonal up-right
        ]
    
    def evaluate_position(self, board: List[List[int]], x: int, y: int, my_stone: int) -> int:
        """Evaluate a position, higher score = better move"""
        opp_stone = 3 - my_stone
        score = 0
        
        # Prioritize blocking opponent's threats over building own
        for dir_pair in self.directions:
            # Count for opponent
            count_opp = 0
            blocked_opp = 0
            (dx1, dy1), (dx2, dy2) = dir_pair
            
            cx, cy = x + dx1, y + dy1
            while 0 <= cx < BOARD_SIZE and 0 <= cy < BOARD_SIZE and board[cy][cx] == opp_stone:
                count_opp += 1
                cx += dx1
                cy += dy1
            if not (0 <= cx < BOARD_SIZE and 0 <= cy < BOARD_SIZE) or board[cy][cx] != 0:
                blocked_opp += 1
            
            cx, cy = x + dx2, y + dy2
            while 0 <= cx < BOARD_SIZE and 0 <= cy < BOARD_SIZE and board[cy][cx] == opp_stone:
                count_opp += 1
                cx += dx2
                cy += dy2
            if not (0 <= cx < BOARD_SIZE and 0 <= cy < BOARD_SIZE) or board[cy][cx] != 0:
                blocked_opp += 1
            
            # Score for blocking opponent
            # four in a row must block - higher priority for defense
            if count_opp >= 4:
                score += 15000  # must block, higher priority
            elif count_opp == 3 and blocked_opp == 0:
                score += 8000  # open three, higher priority to block
            elif count_opp == 3 and blocked_opp == 1:
                score += 2000
            elif count_opp == 2 and blocked_opp == 0:
                score += 300
            elif count_opp == 2 and blocked_opp == 1:
                score += 80
            
            # Count for myself - lower priority for defense-oriented play
            count_my = 0
            blocked_my = 0
            cx, cy = x + dx1, y + dy1
            while 0 <= cx < BOARD_SIZE and 0 <= cy < BOARD_SIZE and board[cy][cx] == my_stone:
                count_my += 1
                cx += dx1
                cy += dy1
            if not (0 <= cx < BOARD_SIZE and 0 <= cy < BOARD_SIZE) or board[cy][cx] != 0:
                blocked_my += 1
            
            cx, cy = x + dx2, y + dy2
            while 0 <= cx < BOARD_SIZE and 0 <= cy < BOARD_SIZE and board[cy][cx] == my_stone:
                count_my += 1
                cx += dx2
                cy += dy2
            if not (0 <= cx < BOARD_SIZE and 0 <= cy < BOARD_SIZE) or board[cy][cx] != 0:
                blocked_my += 1
            
            # Lower score for my own connections - don't prioritize winning
            if count_my >= 4:
                score += 4000  # still winning move, but lower than blocking opponent's four
            elif count_my == 3 and blocked_my == 0:
                score += 2000
            elif count_my == 3 and blocked_my == 1:
                score += 400
            elif count_my == 2 and blocked_my == 0:
                score += 80
            elif count_my == 2 and blocked_my == 1:
                score += 20
        
        # Bonus for center control
        center_dist = abs(x - 7) + abs(y - 7)
        score += (8 - center_dist) * 2
        
        # Extra bonus for spreading out on the board (user requested: fill the whole board)
        # Count empty adjacent spots - more empty = more bonus
        empty_adjacent = 0
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx = x + dx
                ny = y + dy
                if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE and board[ny][nx] == 0:
                    empty_adjacent += 1
        score += empty_adjacent * 3  # more empty neighbors = better for spreading
        
        return score
    
    def find_best_move(self, board: List[List[int]], my_stone: int) -> Optional[Tuple[int, int]]:
        """Find best move according to heuristic"""
        best_score = -1
        best_move = None
        
        # Iterate all empty positions near existing stones
        for y in range(BOARD_SIZE):
            for x in range(BOARD_SIZE):
                if board[y][x] != 0:
                    continue
                
                # Only consider positions adjacent to existing stones
                has_adjacent = False
                for dy in [-1, 0, 1]:
                    for dx in [-1, 0, 1]:
                        if dy == 0 and dx == 0:
                            continue
                        ny = y + dy
                        nx = x + dx
                        if 0 <= ny < BOARD_SIZE and 0 <= nx < BOARD_SIZE and board[ny][nx] != 0:
                            has_adjacent = True
                            break
                    if has_adjacent:
                        break
                if not has_adjacent:
                    continue  # skip isolated empty positions
                
                score = self.evaluate_position(board, x, y, my_stone)
                if score > best_score:
                    best_score = score
                    best_move = (x, y)
        
        # If no adjacent moves, pick center
        if best_move is None:
            if board[7][7] == 0:
                best_move = (7, 7)
            else:
                # find any empty spot near center
                for dy in range(-3, 4):
                    for dx in range(-3, 4):
                        y = 7 + dy
                        x = 7 + dx
                        if 0 <= y < BOARD_SIZE and 0 <= x < BOARD_SIZE and board[y][x] == 0:
                            best_move = (x, y)
                            break
                    if best_move:
                        break
        
        return best_move

def poll_game(api_base: str, match_id: str, user_id: str, interval: float = 1.5):
    """Main polling loop"""
    ai = GomokuAI()
    
    print(f"[START] Starting AI poll for match {match_id}")
    print(f"[INFO] User ID: {user_id}")
    print(f"[INFO] API base: {api_base}")
    print(f"[INFO] Poll interval: {interval}s")
    print(f"[INFO] Strategy: block threats first, evaluate connections")
    
    # api_base is http://domain:port, need to add /api/v1
    if not api_base.endswith("/api/v1"):
        api_base = f"{api_base.rstrip('/')}/api/v1"
    url = f"{api_base}/matches/{match_id}"
    headers = {"X-User-Id": user_id}
    
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
            
            if status == "finished":
                winner = item.get("winnerUserId")
                reason = item.get("winReason", "")
                print(f"[INFO] Game finished. Winner: {winner}, reason: {reason}")
                break
            
            ai_input = item.get("agentInput", {})
            if not ai_input.get("isYourTurn"):
                time.sleep(interval)
                continue
            
            # It's my turn!
            print("[INFO] My turn! Finding best move...")
            
            board = item["board"]
            stone = ai_input.get("yourStone")
            if stone is None:
                # Infer from seating
                if item.get("black", {}).get("userId") == user_id:
                    stone = 1
                else:
                    stone = 2
            
            best = ai.find_best_move(board, stone)
            if best is None:
                print("[ERROR] No available moves found!")
                time.sleep(interval)
                continue
            
            x, y = best
            print(f"[INFO] Best move: ({x}, {y})")
            
            # Generate thought
            import random
            score = ai.evaluate_position(board, x, y, stone)
            if score >= 10000:
                templates = [
                    "堵住了你即将连成四子的威胁 ✋",
                    "必须挡住这个冲四，不然你就要赢了 ✋",
                    "拦住这个四连，稳住局面 🛡️",
                    "这个威胁必须防，我堵住了 ✌️"
                ]
                thought = random.choice(templates)
            elif score >= 5000:
                templates = [
                    "挡住了你的活三，稳住 🛡️",
                    "防住这个活三，不给你冲四的机会 ✋",
                    "这个活三必须堵，我抢先站住了 🛡️",
                    "稳稳防住，慢慢来 ✌️"
                ]
                thought = random.choice(templates)
            elif score >= 8000:
                templates = [
                    "我连成了四子，准备获胜了！🔥",
                    "活四连成，这下你防不住了 😎",
                    "Open-ended four in a row，胜利在望 🏆",
                    "我已经连成四子，这棋稳了 ✨"
                ]
                thought = random.choice(templates)
            else:
                templates = [
                    "这里看起来不错，就走这了 🎯",
                    "我觉得这个位置挺好，落子 🎯",
                    "拓展一下我的连线，慢慢推进 🚶",
                    "抢占这个要点，继续发展 💪",
                    "站下这个位置，看看下一步 🤔",
                    "拓展进攻方向，稳步前进 ✨",
                    "这个位置对我有利，落子 ✓",
                    "继续发展我的攻势，推进 🚀"
                ]
                thought = random.choice(templates)
            
            # Submit move
            move_url = f"{url}/moves"
            body = {
                "x": x,
                "y": y,
                "thought": thought
            }
            move_resp = requests.post(move_url, headers=headers, json=body, timeout=15)
            move_data = move_resp.json()
            
            if move_data.get("ok"):
                print("[INFO] Move accepted")
            else:
                err = move_data.get("error", {}).get("message", "Unknown error")
                print(f"[ERROR] Move rejected: {err}")
            
            time.sleep(interval)
            
        except Exception as e:
            print(f"[ERROR] Exception: {e}")
            time.sleep(interval)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Gomoku AI auto polling player")
    parser.add_argument("--match-id", required=True, help="Match ID")
    parser.add_argument("--user-id", required=True, help="My user ID (X-User-Id)")
    parser.add_argument("--api-url", default="http://43.160.197.143:19100/api/v1", help="API base URL")
    parser.add_argument("--interval", type=float, default=1.5, help="Poll interval in seconds")
    args = parser.parse_args()
    
    poll_game(args.api_url, args.match_id, args.user_id, args.interval)

if __name__ == "__main__":
    main()
