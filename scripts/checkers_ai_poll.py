#!/usr/bin/env python3
"""
Chinese Star Checkers automatic AI polling player
Simple strategy: move towards opponent's camp, prioritize longer jumps
"""

import sys
import time
import requests
import json
from typing import List, Tuple, Dict, Optional

class CheckersAI:
    def __init__(self):
        pass
    
    def get_available_moves(self, board: Dict[str, int], my_stone: int, target_camp: List[Tuple[int, int]]) -> List[Dict]:
        """Get all available moves for AI"""
        moves = []
        # Directions: 6 possible directions in star checkers hex grid
        dirs = [
            (1, 0), (-1, 0),   # horizontal
            (0, 1), (0, -1),   # vertical
            (1, -1), (-1, 1),  # diagonal
        ]
        
        # Find all my stones - board keys are always strings "x,y"
        my_stones = [(int(k.split(',')[0]), int(k.split(',')[1])) for k, v in board.items() if v == my_stone]
        
        for (x, y) in my_stones:
            # Try step move (one step) - only distance = 1 is valid step move
            # In hex coordinates: (±1, 0) or (0, ±1) have distance 1
            # (±1, ∓1) is distance 2, that requires a jump
            for dx, dy in dirs:
                nx = x + dx
                ny = y + dy
                key = f"{nx},{ny}"
                if board.get(key, -1) == 0:  # 0 means empty
                    dist = self._hex_dist((x, y), (nx, ny))
                    if dist == 1:  # only step moves get added here
                        # Evaluate: score based on distance to target camp
                        dist_to_target = self.distance_to_camp(nx, ny, target_camp)
                        # For our seat 1 (bottom camp), target is top-left
                        # smaller q = more left (closer to target camp), smaller r = more up (closer to target camp)
                        q_bonus = -(x - nx)   # moving to smaller q gives bonus
                        r_bonus = -(y - ny)   # moving to smaller r gives bonus
                        moves.append({
                            "from": (x, y),
                            "to": (nx, ny),
                            "score": -dist_to_target + q_bonus + r_bonus,  # closer = better, more progress towards target in both axes = better
                            "jumps": 1
                        })
            
            # Try jump moves (over another stone) - recursive
            self.find_jump_moves(x, y, x, y, board, my_stone, 1, [], moves, target_camp)
        
        # Sort by score
        moves.sort(key=lambda m: (-m["score"], -m["jumps"]))
        return moves
    
    def find_jump_moves(self, start_x: int, start_y: int, curr_x: int, curr_y: int, 
                       board: Dict[str, int], my_stone: int, jumps: int, 
                       visited: List[Tuple[int, int]], 
                       result: List[Dict], target_camp: List[Tuple[int, int]]):
        """Find all possible jump sequences"""
        dirs = [
            (2, 0), (-2, 0),
            (0, 2), (0, -2),
            (2, -2), (-2, 2),
        ]
        
        for dx, dy in dirs:
            nx = curr_x + dx
            ny = curr_y + dy
            mid_x = curr_x + dx // 2
            mid_y = curr_y + dy // 2
            mid_key = f"{mid_x},{mid_y}"
            new_key = f"{nx},{ny}"
            
            if (nx, ny) in visited:
                continue
            
            # Check if middle has a stone (any color) and landing is empty
            if board.get(mid_key, 0) != 0 and board.get(new_key, 0) == 0:
                dist = self.distance_to_camp(nx, ny, target_camp)
                # For our seat 1 (bottom camp), target is top-left
                # smaller q = more left (closer to target camp), smaller r = more up (closer to target camp)
                q_bonus = -(start_x - nx)   # moving to smaller q gives bonus
                r_bonus = -(start_y - ny)   # moving to smaller r gives bonus
                result.append({
                    "from": (start_x, start_y),
                    "to": (nx, ny),
                    "score": -dist - jumps * 2 + q_bonus + r_bonus,  # more jumps = better, closer = better, more progress towards target in both axes = better
                    "jumps": jumps + 1
                })
                visited.append((nx, ny))
                self.find_jump_moves(start_x, start_y, nx, ny, board, my_stone, 
                                   jumps + 1, visited, result, target_camp)
    
    def _hex_dist(self, a: tuple[int, int], b: tuple[int, int]) -> int:
        return (
            abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs((-a[0] - a[1]) - (-b[0] - b[1]))
        ) // 2

    def distance_to_camp(self, x: int, y: int, target_camp: List[Tuple[int, int]]) -> int:
        """Calculate minimum distance to target camp"""
        min_dist = 999
        for (tx, ty) in target_camp:
            # Manhattan distance on hex grid
            dist = abs(x - tx) + abs(y - ty)
            if dist < min_dist:
                min_dist = dist
        return min_dist
    
    def find_best_move(self, board: Dict[str, int], my_stone: int, 
                      target_camp: List[Tuple[int, int]]) -> Optional[Tuple[int, int, int, int]]:
        """Find the best move according to simple strategy"""
        moves = self.get_available_moves(board, my_stone, target_camp)
        if not moves:
            return None
        
        best = moves[0]
        return best["from"][0], best["from"][1], best["to"][0], best["to"][1]

def poll_game(api_base: str, match_id: str, user_id: str, interval: float = 2.0):
    """Main polling loop"""
    ai = CheckersAI()
    
    print(f"[START] Starting AI poll for match {match_id}")
    print(f"[INFO] User ID: {user_id}")
    print(f"[INFO] API base: {api_base}")
    print(f"[INFO] Poll interval: {interval}s")
    print(f"[INFO] Strategy: greedy distance to target, prioritize longer jumps")
    
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
            my_seat = None
            my_stone = None
            
            # Figure out which seat I am
            for seat in item["checkersSeats"]:
                if seat["userId"] == user_id:
                    my_seat = seat["seat"]
                    break
            
            # Get target camp from API
            target_camp_map = item["checkersCampKeys"]
            if my_seat == 1:
                my_stone = 1
                target_camp_coords = target_camp_map["1"]
            else:
                my_stone = 2
                target_camp_coords = target_camp_map["2"]
            
            # Convert to list of tuples - all coords are strings from JSON
            target_camp = []
            for k in target_camp_coords:
                if isinstance(k, str):
                    x, y = map(int, k.split(','))
                    target_camp.append((x, y))
                elif isinstance(k, (tuple, list)) and len(k) == 2:
                    target_camp.append((int(k[0]), int(k[1])))
            
            best = ai.find_best_move(board, my_stone, target_camp)
            if best is None:
                print("[ERROR] No available moves found!")
                time.sleep(interval)
                continue
            
            fx, fy, tx, ty = best
            print(f"[INFO] Best move: ({fx}, {fy}) → ({tx}, {ty})")
            
            # Generate thought for danmaku
            if abs(fx - tx) >= 2:
                thought = "跳了一大步，往目标营地前进 💨"
            else:
                thought = "慢慢往前挪，稳步推进 🚶"
            
            # Submit move - checkers requires path array: from first to last, each step is a coordinate
            # Board will be updated automatically by backend: clear start, place at end
            move_url = f"{url}/moves"
            body = {
                "path": [[fx, fy], [tx, ty]],
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
    parser = argparse.ArgumentParser(description="Chinese Star Checkers AI auto polling player")
    parser.add_argument("--match-id", required=True, help="Match ID")
    parser.add_argument("--user-id", required=True, help="My user ID (X-User-Id)")
    parser.add_argument("--api-url", default="http://43.160.197.143:19100/api/v1", help="API base URL")
    parser.add_argument("--interval", type=float, default=2.0, help="Poll interval in seconds")
    args = parser.parse_args()
    
    poll_game(args.api_url, args.match_id, args.user_id, args.interval)

if __name__ == "__main__":
    main()
