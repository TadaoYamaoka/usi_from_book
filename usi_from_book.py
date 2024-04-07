import numpy as np
from cshogi import *
from concurrent.futures import ThreadPoolExecutor

DEFAULT_BOOK = "book.bin"
DEFAULT_MULTIPV = 10
DEFAULT_EVAL_COEF = 756
DEFAULT_DRAW_EVAL = 30
DEFAULT_PV_DEPTH = 1


class Player:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.future = None
        self.board = Board()
        self.book_path = DEFAULT_BOOK
        self.multipv = DEFAULT_MULTIPV
        self.eval_coef = DEFAULT_EVAL_COEF
        self.draw_eval = DEFAULT_DRAW_EVAL
        self.pv_depth = DEFAULT_PV_DEPTH

    def usi(self):
        print("id name usi_from_book")
        print(f"option name BookFile type string default {DEFAULT_BOOK}")
        print(f"option name MultiPV type spin default {DEFAULT_MULTIPV} min 1 max 10")
        print(
            f"option name EvalCoef type spin default {DEFAULT_EVAL_COEF} min 1 max 10000"
        )
        print(
            f"option name DrawEval type spin default {DEFAULT_DRAW_EVAL} min 0 max 10000"
        )
        print(
            f"option name PVDepth type spin default {DEFAULT_PV_DEPTH} min 0 max 1000"
        )

    def usinewgame(self):
        pass

    def setoption(self, args):
        if args[1] == "BookFile":
            self.book_path = args[3]
        elif args[1] == "MultiPV":
            self.multipv = int(args[3])
        elif args[1] == "EvalCoef":
            self.eval_coef = int(args[3])
        elif args[1] == "DrawEval":
            self.draw_eval = int(args[3])
        elif args[1] == "PVDepth":
            self.pv_depth = int(args[3])

    def isready(self):
        self.book = np.fromfile(self.book_path, BookEntry)
        self.book_key = self.book["key"]

    def position(self, sfen, usi_moves):
        if sfen == "startpos":
            self.board.reset()
        elif sfen[:5] == "sfen ":
            self.board.set_sfen(sfen[5:])

        for usi_move in usi_moves:
            self.board.push_usi(usi_move)

    def set_limits(
        self,
        btime=None,
        wtime=None,
        byoyomi=None,
        binc=None,
        winc=None,
        nodes=None,
        infinite=False,
        ponder=False,
    ):
        pass

    def get_entry(self, key):
        index = np.searchsorted(self.book_key, key)
        if index >= len(self.book_key) or self.book_key[index] != key:
            return None
        return self.book[index]

    def get_entries(self, key):
        index = np.searchsorted(self.book_key, key)
        if index >= len(self.book_key) or self.book_key[index] != key:
            return None
        index_r = np.searchsorted(self.book_key, key, "right")
        return self.book[index:index_r]
    
    def get_pv(self, move16, depth):
        pv = [move16]
        if depth > 0:
            self.board.push_move16(move16)
            draw = self.board.is_draw()
            if draw not in (REPETITION_DRAW, REPETITION_WIN, REPETITION_LOSE):
                entry = self.get_entry(self.board.book_key())
                if entry is not None:
                    pv.extend(self.get_pv(entry["fromToPro"], depth - 1))
            self.board.pop()
        return pv

    def go(self):
        pv_list = []
        entries = self.get_entries(self.board.book_key())
        if entries is None:
            return "resign", None
        else:
            for entry in entries:
                pv_list.append(
                    [
                        move_to_usi(entry["fromToPro"]),
                        entry["score"],
                        self.get_pv(entry["fromToPro"], self.pv_depth),
                    ]
                )
                if len(pv_list) >= self.multipv:
                    break

        for pv in pv_list:
            self.board.push_usi(pv[0])
            draw = self.board.is_draw()
            if draw == REPETITION_DRAW:
                pv[1] = self.draw_eval * (-1 if self.board.turn == WHITE else 1)
            elif draw == REPETITION_WIN:
                pv[1] = -30000
            elif draw == REPETITION_LOSE:
                pv[1] = 30000
            self.board.pop()

        if self.multipv == 1:
            pv = pv_list[0]
            print(f"info score cp {pv[1]} pv {' '.join(move_to_usi(move) for move in pv[2])}")
        else:
            for i, pv in enumerate(pv_list):
                print(
                    f"info multipv {i + 1} score cp {pv[1]} pv {' '.join(move_to_usi(move) for move in pv[2])}"
                )
                if i + 1 >= self.multipv:
                    break
        return pv_list[0][0], None

    def stop(self):
        pass

    def ponderhit(self, last_limits):
        pass

    def quit(self):
        pass

    def run(self):
        while True:
            cmd_line = input().strip()
            cmd = cmd_line.split(" ", 1)

            if cmd[0] == "usi":
                self.usi()
                print("usiok", flush=True)
            elif cmd[0] == "setoption":
                option = cmd[1].split(" ")
                self.setoption(option)
            elif cmd[0] == "isready":
                self.isready()
                print("readyok", flush=True)
            elif cmd[0] == "usinewgame":
                self.usinewgame()
            elif cmd[0] == "position":
                args = cmd[1].split("moves")
                self.position(args[0].strip(), args[1].split() if len(args) > 1 else [])
            elif cmd[0] == "go":
                kwargs = {}
                if len(cmd) > 1:
                    args = cmd[1].split(" ")
                    if args[0] == "infinite":
                        # kwargs["infinite"] = True
                        pass
                    else:
                        if args[0] == "ponder":
                            kwargs["ponder"] = True
                            args = args[1:]
                        for i in range(0, len(args) - 1, 2):
                            if args[i] in [
                                "btime",
                                "wtime",
                                "byoyomi",
                                "binc",
                                "winc",
                                "nodes",
                            ]:
                                kwargs[args[i]] = int(args[i + 1])
                self.set_limits(**kwargs)
                # ponderhitのために条件と経過時間を保存
                last_limits = kwargs
                need_print_bestmove = (
                    "ponder" not in kwargs and "infinite" not in kwargs
                )

                def go_and_print_bestmove():
                    bestmove, ponder_move = self.go()
                    if need_print_bestmove:
                        print(
                            "bestmove "
                            + bestmove
                            + (" ponder " + ponder_move if ponder_move else ""),
                            flush=True,
                        )
                    return bestmove, ponder_move

                self.future = self.executor.submit(go_and_print_bestmove)
            elif cmd[0] == "stop":
                need_print_bestmove = False
                self.stop()
                bestmove, _ = self.future.result()
                print("bestmove " + bestmove, flush=True)
            elif cmd[0] == "ponderhit":
                last_limits["ponder"] = False
                self.ponderhit(last_limits)
                bestmove, ponder_move = self.future.result()
                print(
                    "bestmove "
                    + bestmove
                    + (" ponder " + ponder_move if ponder_move else ""),
                    flush=True,
                )
            elif cmd[0] == "quit":
                self.quit()
                break


Player().run()
