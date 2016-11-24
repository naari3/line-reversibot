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

import pprint
pp = pprint.PrettyPrinter(indent=4)

from __future__ import unicode_literals

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
win_string = config["win_string"]
lose_string = config["lose_string"]

# get channel_secret and channel_access_token from your environment variable
channel_secret = os.getenv('LINE_CHANNEL_SECRET', None)
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', None)
if channel_secret is None:
    print('Specify LINE_CHANNEL_SECRET as environment variable.')
    sys.exit(1)
if channel_access_token is None:
    print('Specify LINE_CHANNEL_ACCESS_TOKEN as environment variable.')
    sys.exit(1)

line_bot_api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)

static_tmp_path = os.path.join(os.path.dirname(__file__), 'static', 'tmp')

# function for create tmp dir for download content
def make_static_tmp_dir():
    try:
        os.makedirs(static_tmp_path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(static_tmp_path):
            pass
        else:
            raise

@app.route('/boards/<user_id>/<timestump>/<int:size>')
def board_images(user_id=None, timestump=None, size=1040):
    user = reversies.get(user_id, None)
    if user is None or timestump is None:
        return 'NG'
    buf = BytesIO()
    user.board_images[timestump][size].save(buf, 'png')
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

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    pp.pprint(reversies)
    text = event.message.text

    if text == 'オセロ':
        if isinstance(event.source, SourceUser):
            profile = line_bot_api.get_profile(event.source.user_id)
        turn = random.randint(1,2)
        reversies[profile.user_id] = Reversi(turn)
        if turn == 2:
            reversies[profile.user_id].ai_turn_proccess()
        putable = reversies[profile.user_id].able_to_put()
        timestump = reversies[profile.user_id].update_board_images()
        textmessage = TextSendMessage(
            text=your_turn_format.format(profile.display_name, (first_attack) if (turn == 1) else (second_attack))
        )
        print("/boards/{}/{}/{}".format(profile.user_id, timestump, 1040))
        imagemap = make_reversi_imagemap(profile.user_id, timestump, putable)
        try:
            line_bot_api.reply_message(event.reply_token, [textmessage, imagemap])
        except Exception as e:
            print(e.error.details)

    elif input_format.match(text):
        if isinstance(event.source, SourceUser):
            profile = line_bot_api.get_profile(event.source.user_id)
        x, y = text
        x = ord(x) - 97 # str:[a-h] -> int:[0-7]
        y = int(y) - 1 # int:[0-7]
        p = y * 8 + x
        print(p)
        reversies[profile.user_id].put_piece(p, reversies[profile.user_id].turn)
        reversies[profile.user_id].ai_turn_proccess()
        putable = reversies[profile.user_id].able_to_put()
        if putable:
            timestump = reversies[profile.user_id].update_board_images()
            imagemap = make_reversi_imagemap(profile.user_id, timestump, putable)
            line_bot_api.reply_message(event.reply_token, [imagemap])
        else:
            score1 = (reversies[profile.user_id].board==1).sum()
            score2 = (reversies[profile.user_id].board==2).sum()
            turn = reversies[profile.user_id].turn
            if (score1 > score2 and turn == 1) or (score2 > score1 and turn == 2):
                judge = True
            else:
                judge = False
            textmessage = TextSendMessage(
                text = finish_format.format(score1, score2, (win_string) if judge else (lose_string))
            )
            timestump = reversies[profile.user_id].update_board_images()
            imagemap = make_reversi_imagemap(profile.user_id, timestump, putable)
            line_bot_api.reply_message(event.reply_token, [imagemap, textmessage])

    else:
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


# Other Message Type
@handler.add(MessageEvent, message=(ImageMessage, VideoMessage, AudioMessage))
def handle_content_message(event):
    if isinstance(event.message, ImageMessage):
        ext = 'jpg'
    elif isinstance(event.message, VideoMessage):
        ext = 'mp4'
    elif isinstance(event.message, AudioMessage):
        ext = 'm4a'
    else:
        return

    message_content = line_bot_api.get_message_content(event.message.id)
    with tempfile.NamedTemporaryFile(dir=static_tmp_path, prefix=ext + '-', delete=False) as tf:
        for chunk in message_content.iter_content():
            tf.write(chunk)
        tempfile_path = tf.name

    dist_path = tempfile_path + '.' + ext
    dist_name = os.path.basename(dist_path)
    os.rename(tempfile_path, dist_path)

    line_bot_api.reply_message(
        event.reply_token, [
            TextSendMessage(text='Save content.'),
            TextSendMessage(text=request.host_url + os.path.join('static', 'tmp', dist_name))
        ])


@handler.add(FollowEvent)
def handle_follow(event):
    line_bot_api.reply_message(
        event.reply_token, TextSendMessage(text='Got follow event'))

@handler.add(UnfollowEvent)
def handle_unfollow():
    app.logger.info("Got Unfollow event")

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

def make_reversi_imagemap(user_id, timestump, putable):
    imagemap_message = ImagemapSendMessage(
        base_url=hostname + "/boards/{}/{}".format(user_id, timestump),
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

    # create tmp dir for download content
    make_static_tmp_dir()

    app.run(debug=options.debug, port=options.port)
