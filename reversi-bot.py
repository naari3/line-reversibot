# -*- coding: utf-8 -*-

#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.

from __future__ import unicode_literals

import pprint
pp = pprint.PrettyPrinter(indent=4)

import errno
import os
import sys
import tempfile
from argparse import ArgumentParser

from io import BytesIO

from flask import Flask, request, abort, send_file

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    ImagemapSendMessage, BaseSize, MessageImagemapAction, ImagemapArea,
    MessageEvent, TextMessage, TextSendMessage,
    SourceUser, SourceGroup, SourceRoom,
    TemplateSendMessage, ConfirmTemplate, MessageTemplateAction,
    ButtonsTemplate, URITemplateAction, PostbackTemplateAction,
    CarouselTemplate, CarouselColumn, PostbackEvent,
    StickerMessage, StickerSendMessage, LocationMessage, LocationSendMessage,
    ImageMessage, VideoMessage, AudioMessage,
    UnfollowEvent, FollowEvent, JoinEvent, LeaveEvent, BeaconEvent
)

from reversi import Reversi
import random, re

import yaml

input_format = re.compile(r'[a-h][1-8]')

reversies = {}

app = Flask(__name__)

with open("config.yml") as f:
    fdata = f.read()
config = yaml.load(fdata)

hostname = config["hostname"]

your_turn_format = config["your_turn_format"]
first_attack = config["first_attack"]
second_attack = config["second_attack"]
finish_format = config["finish_format"]
draw_format = config["draw_format"]
win_string = config["win_string"]
lose_string = config["lose_string"]
ai_passing = config["ai_passing"]
your_passing = config["your_passing"]
ai_passmessage = TextSendMessage(text = ai_passing)
your_passmessage = TextSendMessage(text = your_passing)
helptext = config["help"]
help_message = TextSendMessage(text = helptext)

# import os
import psycopg2
import six.moves.urllib_parse as urlparse

urlparse.uses_netloc.append("postgres")
url = urlparse.urlparse(os.environ["DATABASE_URL"])

conn = psycopg2.connect(
    database=url.path[1:],
    user=url.username,
    password=url.password,
    host=url.hostname,
    port=url.port
)

channel_secret = os.getenv('LINE_CHANNEL_SECRET', None)
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', None)
try:
    with open("auth.yml") as af:
        afdata = af.read()
    auth = yaml.load(afdata)
    channel_secret = auth["LINE_CHANNEL_SECRET"]
    channel_access_token = auth["LINE_CHANNEL_ACCESS_TOKEN"]
except Exception as e: # auth.yml is in .gitignore
    pass
if channel_secret is None:
    print('You need to set LINE_CHANNEL_SECRET.')
    sys.exit(1)
if channel_access_token is None:
    print('You need to set LINE_CHANNEL_ACCESS_TOKEN.')
    sys.exit(1)

line_bot_api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)

# static_tmp_path = os.path.join(os.path.dirname(__file__), 'static', 'tmp')

@app.route('/')
def index():
    return "OK"

@app.route('/boards/<data>/<int:size>')
def board_images(data=None, size=1040):
    if data is None:
        return 'NG'
    r = Reversi()
    r.insert(data)
    r.create_board_images()
    r.update_board_images()
    buf = BytesIO()
    r.board_images[size].save(buf, 'png')
    buf.seek(0,0)
    return send_file(buf, mimetype='image/png')

@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

def insert_to_table(user_id, data):
    cur = conn.cursor()
    cur.execute("INSERT INTO reversi (user_id, data) VALUES (%s, %s) ON CONFLICT ON CONSTRAINT reversi_pkey DO UPDATE SET data = %s",(user_id, data, data))
    conn.commit()
    cur.close()

def select_from_table(user_id):
    cur = conn.cursor()
    cur.execute("SELECT data FROM reversi WHERE user_id = %s", [user_id])
    d = cur.fetchone()
    data = None
    if d:
        data = d[0]
    cur.close()
    return data

def update_reversi_result(user_id, result): # result -> 1: win, 2: lose, 3: draw
    cur = conn.cursor()
    rslt = ""
    winint, loseint, drawint = 0, 0, 0
    if result == 1:
        rslt = "win"
        winint += 1
    elif result == 2:
        rslt = "lose"
        loseint += 1
    elif result == 3:
        rslt = "draw"
        drawint += 1
    cur.execute("INSERT INTO reversi_result VALUES (%s, %s, %s, %s) ON CONFLICT (user_id) DO UPDATE SET "+rslt+" = reversi_result."+rslt+" + 1", (user_id, winint, loseint, drawint))
    conn.commit()
    cur.close()

def select_reversi_result(user_id):
    cur = conn.cursor()
    cur.execute("SELECT win, lose, draw FROM reversi_result WHERE user_id = %s", [user_id])
    d = cur.fetchone()
    data = None
    if d:
        data = d # (int(win), int(lose), int(draw))
    cur.close()
    return data


@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    text = event.message.text
    print(text)

    if isinstance(event.source, SourceUser):
        talk_type = 'user'
        talk_id = event.source.user_id
        profile = line_bot_api.get_profile(event.source.user_id)
        display_name = "{}さん".format(profile.display_name)
    elif isinstance(event.source, SourceGroup):
        talk_type = 'group'
        talk_id = event.source.group_id
        display_name = 'このグループ'
    elif isinstance(event.source, SourceRoom):
        talk_type = 'room'
        talk_id = event.source.room_id
        display_name = 'このルーム'

    if text == 'オセロ':
        message_stack = []
        turn = random.randint(1,2)
        reversi = Reversi(turn)
        data = select_from_table(talk_id)
        if data:
            r = Reversi()
            r.insert(data) # reversi.guideを参照したいために (時間の都合上)
            reversi.guide = r.guide
        if turn == 2:
            ai_p = reversi.best(reversi.ai_turn)
            reversi.put_piece(ai_p, reversi.ai_turn)
            y, x = divmod(ai_p, 8)
            ai_putmessage = TextSendMessage(
                text = "{}{}".format(chr(97+y), x+1)
            )
            message_stack.append(ai_putmessage)
        putable = reversi.able_to_put()
        text = your_turn_format.format(display_name, (first_attack) if (turn == 1) else (second_attack))
        turn_notice_message = TextSendMessage(text=text)
        message_stack.append(turn_notice_message)
        data = reversi.extract()
        insert_to_table(talk_id, data)
        print("/boards/{}/{}".format(data, 1040))
        imagemap = make_reversi_imagemap(data, putable)
        message_stack.append(imagemap)
        try:
            line_bot_api.reply_message(event.reply_token, message_stack)
        except Exception as e:
            print(e.error.details)

    elif text == 'reload' or text == 'リロード':
        data = select_from_table(talk_id)
        reversi = Reversi()
        reversi.insert(data)
        putable = reversi.able_to_put()
        imagemap = make_reversi_imagemap(data, putable)
        line_bot_api.reply_message(event.reply_token, [imagemap])

    elif input_format.match(text):
        message_stack = []
        x, y = text
        x = ord(x) - 97 # str:[a-h] -> int:[0-7]
        y = int(y) - 1 # int:[0-7]
        p = y * 8 + x
        print(p, talk_id, display_name)
        data = select_from_table(talk_id)
        reversi = Reversi()
        reversi.insert(data)
        reversi.put_piece(p, reversi.turn)
        ai_p = reversi.best(reversi.ai_turn)
        if ai_p == -1 and (reversi.board==0).sum():
            message_stack.append(ai_passmessage)
        else:
            reversi.put_piece(ai_p, reversi.ai_turn)
            y, x = divmod(ai_p, 8)
            ai_putmessage = TextSendMessage(
                text = "{}{}".format(chr(97+y), x+1)
            )
            message_stack.append(ai_putmessage)
        putable = reversi.able_to_put()
        data = reversi.extract()
        insert_to_table(talk_id, data)
        imagemap = make_reversi_imagemap(data, putable)
        message_stack.append(imagemap)
        while not reversi.able_to_put() and reversi.able_to_put(reversi.ai_turn):
            message_stack.append(your_passmessage)
            ai_p = reversi.best(reversi.ai_turn)
            reversi.put_piece(ai_p, reversi.ai_turn)
            y, x = divmod(ai_p, 8)
            ai_putmessage = TextSendMessage(
                text = "{}{}".format(chr(97+y), x+1)
            )
            message_stack.append(ai_putmessage)

            putable = reversi.able_to_put()
            data = reversi.extract()
            insert_to_table(talk_id, data)
            imagemap = make_reversi_imagemap(data, putable)
            message_stack.append(imagemap)
        else:
            if not reversi.able_to_put():
                score1 = (reversi.board==1).sum()
                score2 = (reversi.board==2).sum()
                turn = reversi.turn
                judge = False
                draw = False
                if score1 == score2:
                    draw = True
                elif (score1 > score2 and turn == 1) or (score2 > score1 and turn == 2):
                    judge = True
                else:
                    judge = False
                if draw:
                    finish_message = TextSendMessage(
                        text = draw_format.format(score1, score2)
                    )
                    update_reversi_result(talk_id, 3)
                else:
                    finish_message = TextSendMessage(
                        text = finish_format.format(score1, score2, (win_string) if judge else (lose_string))
                    )
                    update_reversi_result(talk_id, 1 if judge else 2)
                message_stack.append(finish_message)
        line_bot_api.reply_message(event.reply_token, message_stack)


    elif text == 'guide on' or text == 'guide off' or text == 'guide switch':
        data = select_from_table(talk_id)
        reversi = Reversi()
        reversi.insert(data)
        if 'on' in text:
            reversi.guide = True
        if 'off' in text:
            reversi.guide = False
        if 'switch' in text:
            reversi.guide = not reversi.guide
        data = reversi.extract()
        insert_to_table(talk_id, data)
        putable = reversi.able_to_put()
        imagemap = make_reversi_imagemap(data, putable)
        line_bot_api.reply_message(event.reply_token, [imagemap])

    elif text == 'オセロ help' or text == 'オセロ ヘルプ':
        line_bot_api.reply_message(event.reply_token, [help_message])

    elif text == '戦績確認':
        results = select_reversi_result(talk_id)
        if results:
            result_message = TextSendMessage(text="{}の戦績\nwin: {}\nlose: {}\ndraw: {}".format(display_name, *results))
        else:
            result_message = TextSendMessage(text="記録がありません")
        line_bot_api.reply_message(event.reply_token, [result_message])

    elif text == '@bye':
        if isinstance(event.source, SourceGroup):
            line_bot_api.leave_group(event.source.group_id)
        elif isinstance(event.source, SourceRoom):
            line_bot_api.leave_room(event.source.room_id)
        else:
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="？"))

    else:
        if isinstance(event.source, SourceUser):
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text=event.message.text))

@handler.add(MessageEvent, message=StickerMessage)
def handle_sticker_message(event):
    line_bot_api.reply_message(
        event.reply_token,
        StickerSendMessage(
            package_id=event.message.package_id,
            sticker_id=event.message.sticker_id)
    )

@handler.add(PostbackEvent)
def handle_postback(event):
    if event.postback.data == 'ping':
        line_bot_api.reply_message(
            event.reply_token, TextSendMessage(text='pong'))

def make_reversi_area(x, y):
    area = ImagemapArea(
        x = x * 130,
        y = y * 130,
        width = 130,
        height = 130,
    )
    return area

def make_reversi_action(p):
    y, x = divmod(p, 8)
    i2a = str.maketrans("01234567", "abcdefgh") # int to alphabet
    text = '{}{}'.format(str(x).translate(i2a), y+1)
    action = MessageImagemapAction(
        text = text,
        area = make_reversi_area(x, y),
    )
    return action

def make_reversi_imagemap(data, putable):
    imagemap_message = ImagemapSendMessage(
        base_url=hostname + "/boards/{}".format(data),
        alt_text='reversi board',
        base_size=BaseSize(height=1040, width=1040),
        actions=[make_reversi_action(p) for p in putable]
    )
    return imagemap_message

if __name__ == "__main__":
    arg_parser = ArgumentParser(
        usage='Usage: python ' + __file__ + ' [--port <port>] [--help]'
    )
    arg_parser.add_argument('-p', '--port', default=8000, help='port')
    arg_parser.add_argument('-d', '--debug', default=False, help='debug')
    options = arg_parser.parse_args()

    app.run(debug=options.debug, port=options.port)
