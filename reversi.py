import numpy as np
from PIL import Image, ImageDraw, ImageFont
import time
import datetime
import json
import base64

font_name = 'Roboto-Black.ttf'

BG = (0, 153, 76)
text_color = (30, 183, 106)
White = (255, 255, 255)
Black = (0, 0, 0)

# Thanks for http://qiita.com/Tsutomu-KKE@github/items/5824eb00250bf08f9197
class Reversi(object):
    """docstring for reversi."""
    def __init__(self, turn=None):
        self.sizes = [1040, 700, 460, 300, 240]
        self.size_fixers = {
            1040: {"image_size": (1040, 1040), "board_size": 1040, "square_size": 130, "piece_size_diff": 5, "side_space": 0, "font_size": 50}, # font_size / square_size -> 38.46%
            700:  {"image_size": (700,  700),  "board_size": 696,  "square_size": 87,  "piece_size_diff": 2, "side_space": 2, "font_size": 33},
            460:  {"image_size": (460,  460),  "board_size": 456,  "square_size": 57,  "piece_size_diff": 2, "side_space": 2, "font_size": 22},
            300:  {"image_size": (300,  300),  "board_size": 296,  "square_size": 37,  "piece_size_diff": 2, "side_space": 2, "font_size": 14},
            240:  {"image_size": (240,  240),  "board_size": 240,  "square_size": 30,  "piece_size_diff": 2, "side_space": 0, "font_size": 12},
        }
        if turn:
            self.turn = turn
            self.ai_turn = 3 - turn
        self.board = self.create_board()
        self.board_images = {}
        self.guide = False
        self.create_board_images()
        self.update_board_images()
    def create_board(self):
        a = np.zeros(64, dtype=int)
        a[27] = a[36] = 1
        a[28] = a[35] = 2
        return a
    def print_board(self):
        print('  a b c d e f g h')
        for i in range(8):
            print(i+1, end=' ')
            print(' '.join('.*o'[j] for j in self.board[i*8:][:8]))
    def put_piece(self, p, w, puton=True, chk=True, other_board=None):
        if isinstance(p, list):
            p = (p[0])+p[1]*8
            if p > 63:
                p = (p[0]-1)+(p[1]-1)*8
        t, x, y = 0, p%8, p//8
        for di, fi in zip([-1, 0, 1], [x, 7, 7-x]):
            for dj, fj in zip([-8, 0, 8], [y, 7, 7-y]):
                if not di == dj == 0:
                    if other_board:
                        b = other_board[p+di+dj::di+dj][:min(fi, fj)]
                    else:
                        b = self.board[p+di+dj::di+dj][:min(fi, fj)]
                    n = (b==3-w).cumprod().sum()
                    if b.size <= n or b[n] != w: n = 0
                    t += n
                    if puton:
                        b[:n] = w
        if puton:
            if other_board:
                if chk: assert(other_board[p] == 0 and t > 0)
                other_board[p] = w
            else:
                if chk: assert(self.board[p] == 0 and t > 0)
                self.board[p] = w
        return t
    def best(self, w):
        known_good_square = [0, 7, 56, 63]
        known_too_bad_square = [9, 14, 49, 54]
        known_bad_square = [1, 6, 8, 15, 48, 55, 57, 62]
        from math import exp
        r, b, c = [], self.board.copy(), 1+exp(-np.count_nonzero(self.board)/16)
        for i in range(64):
            score = 0
            standard = 0
            if b[i] != 0: continue
            t = put_piece(b, i, w, True, False)
            if t == 0:
                b[i] = 0
                continue
            u = sum(b[j]==0 and self.put_piece(j, 3-w, False, b) > 0 for j in range(64))
            bb = Reversi(self.turn)
            bb.board = b
            enemy_putables = bb.able_to_put()
            print("next enemy moves", enemy_putables)
            for ep in enemy_putables:
                if ep in known_good_square:
                    standard += -12
            if i in known_good_square:
                standard += 8
            if i in known_too_bad_square:
                standard += -8
            # elif i in known_bad_square:
            #     standard += -c
            score = t-c*u+np.random.rand()*0.5 + standard
            r.append((score, i))
            b = self.board.copy()
        print(sorted(r))
        return sorted(r)[-1][1] if r else -1

    def make_font(self, font_size):
        return ImageFont.truetype(font_name, font_size)

    def calc_pos(self, font, v, text, x, y):
        width, height = font.getsize(text)
        sq_size = self.size_fixers[v]["square_size"]
        x_pos = (sq_size - width) / 2 + sq_size * x
        y_pos = (sq_size - height) / 2 + sq_size * y
        return (x_pos, y_pos)

    def create_board_images(self):
        for v in self.sizes:
            image_size  = self.size_fixers[v]["image_size"]
            board_size  = self.size_fixers[v]["board_size"]
            square_size = self.size_fixers[v]["square_size"]
            side_space  = self.size_fixers[v]["side_space"]
            im = Image.new(mode="RGB",  size=image_size)
            draw = ImageDraw.Draw(im)
            draw.rectangle([(side_space, side_space), (board_size, board_size)], BG,)
            for i in range(8):
                draw.line([(i*square_size+side_space, side_space), (i*square_size+side_space, board_size+side_space)], fill=0)
                draw.line([(side_space, i*square_size+side_space), (board_size+side_space, i*square_size+side_space)], fill=0)
            font = self.make_font(self.size_fixers[v]["font_size"])
            if self.guide:
                putable = self.able_to_put()
                for y in range(8):
                    for x, xt in enumerate("abcdefgh"):
                        if not y*8 + x in putable:
                            continue
                        text = "{}{}".format(xt, y+1)
                        pos = self.calc_pos(font, v, text, x, y)
                        draw.text(pos, text, font=font, fill=text_color)
            self.board_images[v] = im
            del draw

    def put_piece_images(self, p, w):
        for v in self.sizes:
            board_image = self.board_images[v]
            board_size  = self.size_fixers[v]["board_size"]
            square_size = self.size_fixers[v]["square_size"]
            side_space  = self.size_fixers[v]["side_space"]
            piece_size_diff = self.size_fixers[v]["piece_size_diff"]
            draw = ImageDraw.Draw(board_image)
            y, x = divmod(p, 8)
            if w == 1:
                draw.ellipse([(x*square_size+side_space+piece_size_diff, y*square_size+side_space+piece_size_diff), ((x+1)*square_size+side_space-piece_size_diff, (y+1)*square_size+side_space-piece_size_diff)], Black)
            elif w == 2:
                draw.ellipse([(x*square_size+side_space+piece_size_diff, y*square_size+side_space+piece_size_diff), ((x+1)*square_size+side_space-piece_size_diff, (y+1)*square_size+side_space-piece_size_diff)], White)
            self.board_images[v] = board_image
            del draw

    def update_board_images(self):
        for i, v in enumerate(self.board):
            self.put_piece_images(i, v)

    def able_to_put(self, w=None):
        if w is None:
            w = self.turn
        squares = []
        for i in range(64):
            if self.board[i] != 0: continue
            try:
                if self.put_piece(i, w, False) != 0:
                    squares.append(i)
            except: pass
        return squares

    def ai_turn_proccess(self):
        p = self.best(self.ai_turn)
        if p != -1: # -1 == pass
            self.put_piece(p, self.ai_turn)
            return False
        else:
            return True

    def extract(self):
        data = {}
        data["board"] = self.board.tolist()
        data["turn"] = self.turn
        data["guide"] = self.guide
        # zlib.compress(data.encode('utf-8'))
        return base64.b64encode(json.dumps(data).encode('utf-8')).decode('utf-8')

    def insert(self, b64str):
        data = json.loads(base64.b64decode(b64str.encode('utf-8')).decode('utf-8'))
        self.board = np.array(data["board"])
        self.turn = data["turn"]
        self.ai_turn = 3 - data["turn"]
        self.guide = data["guide"]
        self.update_board_images()


def create_board():
    a = np.zeros(64, dtype=int)
    a[27] = a[36] = 1
    a[28] = a[35] = 2
    return a
def print_board(a):
    print('  a b c d e f g h')
    for i in range(8):
        print(i+1, end=' ')
        print(' '.join('.*o'[j] for j in a[i*8:][:8]))
def put_piece(a, p, w, puton=True, chk=True):
    t, x, y = 0, p%8, p//8
    for di, fi in zip([-1, 0, 1], [x, 7, 7-x]):
        for dj, fj in zip([-8, 0, 8], [y, 7, 7-y]):
            if not di == dj == 0:
                b = a[p+di+dj::di+dj][:min(fi, fj)]
                n = (b==3-w).cumprod().sum()
                if b.size <= n or b[n] != w: n = 0
                t += n
                if puton:
                    b[:n] = w
    if puton:
        if chk: assert(a[p] == 0 and t > 0)
        a[p] = w
    return t

def best(a, w):
    from math import exp
    r, b, c = [], a.copy(), 1+exp(-np.count_nonzero(a)/16)
    for i in range(64):
        if b[i] != 0: continue
        t = put_piece(b, i, w, True, False)
        if t == 0:
            b[i] = 0
            continue
        u = sum(b[j]==0 and put_piece(b, j, 3-w, False) > 0 for j in range(64))
        r.append((t-c*u+np.random.rand()*0.5, i))
        b = a.copy()
    return sorted(r)[-1][1] if r else -1


if __name__ == '__main__':
    import random
    a = Reversi(random.randint(1,2))
    while np.count_nonzero(a.board) < 64:
        a.print_board()
        s = input('> ')
        if not s or s=='q': break
        if s != 'p':
            try:
                x, y = ord(s[0])-97, int(s[1])-1
                a.put_piece(x+8*y, a.turn)
            except:
                continue
        p = a.best(a.ai_turn)
        if p >= 0:
            a.put_piece(p, a.ai_turn)
    a.print_board()
    n1, n2 = (a.board==1).sum(), (a.board==2).sum()
    print('%d - %d %s' % (n1, n2,
        'You win' if n1 > n2 else
        'You lose' if n1 < n2 else 'Draw'))
