# /game/phases/movement_phase.py

from objects.dice import roll_d6
from data.keywords import has_keyword

from ..utils import reachable_squares, parse_column_label    # your helper to turn "AA"->int
from ..objective import Objective


ENGAGEMENT_RANGE = 1.0

def movement_phase(game):

    # reset all turn‑flags before any unit moves
    for u in game.current_player().units:
        u.advanced = u.fell_back = False
    game.run_choice_abilities('movement')

    for u in [u for u in game.current_player().units if u.is_alive()]:
        base = u.datasheet['M']

        choice = input(f"{u.name} move [n]ormal/[a]dv/[f]all/[s]tationary: ").lower()

        if choice == 'a':
            boost = roll_d6()[0]
            print(f"Advance roll: {boost}")
            max_move = base + boost
            u.advanced = True

        elif choice == 'f':
            max_move = base
            u.fell_back = True

            # if Battle-shocked, take one Desperate Escape test per model
            if getattr(u, 'battle_shocked', False):
                tests = u.current_models
                print(f"  {u.name} is Battle-shocked! -> Taking Desperate Escape tests for {tests}")
                
                for i in range(1, tests+1):
                    d = roll_d6()[0]
                    if d <= 2:
                        print(f"    Test {i}: {d} -> One model lost")
                        # subtract one model's worth of wounds
                        u.take_damage(u.wounds_per_model)
                print(f"  -> now {u.current_models}/{u.size} models remain\n")
        
        elif choice == 'n':
            # Normal unit movement
            max_move = base
        else:
            # stationary or any other input
            max_move = 0 

        # compute reachable squares
        if u.fell_back:
            # Fall-back: any square ≤ max_move, but cannot end in Engagement Range of any enemy
            moves = set()
            cx, cy = u.position
            for x in range(game.board.width):
                for y in range(game.board.height):
                    # distance check
                    if game.board.distance_inches((cx, cy), (x, y)) <= max_move:
                        # must end on empty or its own start
                        if (x,y) == (cx,cy) or game.board.grid[y][x] == ' ':
                            # ensure not within ER of any enemy
                            too_close = False
                            for opp in game.other_player().units:
                                if not opp.is_alive(): continue
                                if game.board.distance_inches((x,y), opp.position) <= ENGAGEMENT_RANGE:
                                    too_close = True
                                    break
                            if not too_close:
                                moves.add((x,y))
        else:
            # Normal or Advance or Stationary
            # Fly units ignore terrain
            if has_keyword(u, 'unit', 'Fly'):
                # any empty square within move distance
                moves = set()
                cx, cy = u.position
                for x in range(game.board.width):
                    for y in range(game.board.height):

                        # distance applies to both “can stay” or “empty to move into”
                        if game.board.distance_inches((cx,cy),(x,y)) <= max_move \
                           and ((x,y)==(cx,cy) or game.board.grid[y][x]==' '):
                            moves.add((x,y))
            else:
                moves = reachable_squares(u, game.board, max_move)

        # never include starting square
        moves.discard(u.position)

        if not moves:
            print("No valid moves for this unit.\n")
            continue

        # show board with only those squares highlighted
        game.board.display(flip=True, highlight=moves)

        # prompt until a legal destination is entered
        while True:
            code = input("Enter destination (e.g. E10): ").strip().upper()
            valid = False
            for i in range(1, len(code)):
                col_label, row_s = code[:i], code[i:]
                if not row_s.isdigit():
                    continue

                x = parse_column_label(col_label)
                y = int(row_s) - 1
                
                # 1) bounds check
                if not (0 <= x < game.board.width and 0 <= y < game.board.height):
                    print("That coordinate is off the board.")
                    break

                # 2) reachability check
                if (x,y) not in moves:
                    print("That square is not reachable this move.")
                    break

                # 3) occupancy check
                if game.board.grid[y][x] != ' ':
                    print("That square is occupied; choose another.")
                    break

                # if we get here, x,y is good -> perform the move
                game.board.move_unit(u, x, y)
                print(f"{u.name} moved to {col_label}{row_s}\n")
                game.board.display(flip=True)
                
                # now update objective control
                Objective.update_objective_control(game)

                # Exit out of loop
                code = None
                break

            # end for‑i loop
            else:
                # no split yielded a valid digit‑part, try again
                continue
            
            # if we broke out because of a successful move, code was set to None
            if code is None:
                break

            