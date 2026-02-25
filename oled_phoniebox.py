#!/usr/bin/python3
# -*- coding: utf-8 -*-
import base64
import configparser
import io
import math
import os
import re
import signal
import sys
from datetime import timedelta
from enum import Enum
from time import sleep

import RPi.GPIO as GPIO
from PIL import ImageFont, Image, ImageDraw
from luma.core import cmdline, error
from luma.core.image_composition import ImageComposition, ComposableImage
from luma.core.render import canvas
from mpd import MPDClient

# disable warning when a pin is not in IN state on first use. gpio configuration is out of scope of this script and bad initial state does happen
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)


class MpdStatus(Enum):
    PLAY = 1
    PAUSE = 2
    STOP = 3


# TODO change this later. we wanna use splitties led service or implement some other stuff in this repo entirely.
def enable_leds():
    for pin in config["LEDS"]:
        GPIO.setup(config["LEDS"][pin], GPIO.OUT)
        GPIO.output(config["LEDS"][pin], GPIO.HIGH)


def disable_leds():
    for pin in config["LEDS"]:
        GPIO.setup(config["LEDS"][pin], GPIO.IN)


# used googles material for the logos https://fonts.google.com/icons?preview.text=%E2%8F%BB&preview.text_type=custom&icon.set=Material+Icons&icon.query=power
# then IrfanView to convert them:
# image->show channel->alpha (or any)
# ctrl + r 	height 64
# shift v 128x64 center
# image->decrease color depth 2
# saved as png
# then did base64 -w 0 on the images
def get_logo():
    logo = {
        "card": "iVBORw0KGgoAAAANSUhEUgAAAIAAAABACAIAAABdtOgoAAAACXBIWXMAAA7DAAAOwwHHb6hkAAAB+ElEQVR42u2aWRLCMAxDe/9L9ijwxzCQxWuW5ukLmLakkmvLTq8LAAAAAAAAAMAvXhXATBazcsBhCq1dus8VIJVWw0pgPz0/1C61pQBOdqY8+A8RICRabffsZGp7AdoUqySZIkDtChsIYMgYbT0M9xyiWfFGlhYgMFk7q2uRSsP6txEgtUmxCWA7vcj40gKM6Q9V19eGf/v4pXuxYatxCqCqq3sIMHgdWgGKJ/6sWfL58/W+71Wy0FJtkSqfFMX4N1rdkJ8mgJ/6AROYbgKpla6uBjMFiIr6YQLIHwKVbKMFSJ1wBXZqWgEkdXhyK5BnLtsCaKdGfldjcLHpAvgnl0IBvgugs+9t/2LOYPuNgySTNeGRHtXN5l3yuOw3ENXGuG36pp3qmF3DxnsyeX4pI04ftSk2RbDT92SGNQ0jmTroxQjb8GdYPTtCAINvyTALh76Ype2YosiF+pSYhdmZvENdIt2zyvIpdHedPgJEDo6E73IhQHywtycKjWF9kjc9xVlKBr+GsR0CVBmpZRvbvgcCqIcncmMjZ19Vn8+lXh7UEgYl+1ZQb99K1ab+VV7dWYp6oWU0JHfJhj7Jv5AotOdSWsPGMk4BiOsq7+aSkPFHB80M/C2Yx+HAe0rWItWk2wkMTHy6iGqM8TVPeMIAAAAAAAAAYGG8AQ2n/iAeMyP8AAAAAElFTkSuQmCC",
        "music_note": "iVBORw0KGgoAAAANSUhEUgAAAIAAAABACAIAAABdtOgoAAAACXBIWXMAAAsSAAALEgHS3X78AAAC7UlEQVR42u2c23LDIAxE/f8/nc5k+tAmRqxWWoFt8dja2HDQ6gLxccza692ObqtaA2gAw7eatgZQPeP3BHChJa8DsAzq/gDUhvv3QQswbAWgXjm/+6lm8GQAtoU1AC2AMolrAGQPRQwe7gMawL4AiianAayJrxvAdhnmYwGsHPs+MHYDUBeDjvLAYhgNYG4cDWDZsAkS3gE0AMZn3ADAqJ9NAeDqVAAg65rrAUBILAfgUterAkh02qe3BDfI0gHke0FReEPA+N6TwiXu9PpcC/AmTP/+W58Dn27y5W72gtFzHMBpV8j6+P37ks3u6ZvRC9brA+i9ZcT+bBfISFAWDOJeqRM2RjS1JOTp/DpGhIyAIQLwYTHEO5xaHhcRIEhUmbDL/LMA0O/gLUSO9GTq1ZglSMeL9lrIBcB5L9C1TEUGUa0RgDWJGCdciDdygU8BAKYX3xejs5pbURmRwNf1SL4IF4cH7EQgByYl+TVLPD4xli0RBHMAkHvxg1n2iEgXqANAKHhuSXwk4pw7GcmLEdqusQDEHZWddkaGOVJLwgkPzaIyEzbcowIAKO6cD8DDGysGxdOHlHmJAHA5eSIkRdTMUeQx5xANcLhhezukt/6DeTgxy9OixSiUYN42uB/pKsHjGT8972AhCMx4T3uwY1A5gIh9iLb+QQcQiYKQ7IQcQm7gMR0GGFkrQiBOgkar2+7kc8gJNWuN4at3hMCoMV3HHAtTGnrXJBy2bkQebRdEHQpc/EtPnda9Yi2yk+EKST+fe3UA9DymJBCRl0cBJCalib845PbWI2mdynaRiU6hgtupaDct3bJz+kk5AIJnMfQw4oe6FAc7hNFCoi57iyecbtQAyHeN9R+7KKi8ik56SfKSsvQH2apOH4itYFt8/6byLKIi+SJim2O3VnAEWgHgbh9mkkqZTm165lEx7akXTqsawA2/BKeoZylKFw+d932w3V9qFBIRrCm1T11QUOp2mYy6W4cr3bp1y2o/Mlebfph8u10AAAAASUVORK5CYII=",
        "pause": "iVBORw0KGgoAAAANSUhEUgAAAIAAAABAAQMAAADoGO08AAAABlBMVEUAAAD///+l2Z/dAAAACXBIWXMAAB7CAAAewgFu0HU+AAAAJklEQVQ4jWNgGFpA/v8P/v8/kATs//+Q//9nVGBUYFgIICftoQAAWYK9iYl2zxoAAAAASUVORK5CYII=",
        "pause_circle": "iVBORw0KGgoAAAANSUhEUgAAAIAAAABAAQMAAADoGO08AAAABlBMVEUAAAD///+l2Z/dAAAACXBIWXMAAB7CAAAewgFu0HU+AAAAr0lEQVQ4ja2TQQ7DIAwEQTlw5Al5Sp6WPC1P4Qkcc6i6hVAp3iVtqiq+eWTwYtbO/R1ewfzkPAArgQhsBCbgQQAlqEcFiwFDBYnvBLIC22Y6BVbrrAAQIQp8A4eyoYH1K4jZai/jCUlAVBCyfV1sFQTuqthuqLhXadCK9zwuJkbg+l+6r3QfwJH3htktZa08ngLrws64Qa3tWajr16P25aUb+c79vYmAkxMlFgW/xwuNGicFlFNGbAAAAABJRU5ErkJggg==",
        "play": "iVBORw0KGgoAAAANSUhEUgAAAIAAAABAAQMAAADoGO08AAAABlBMVEUAAAD///+l2Z/dAAAACXBIWXMAAB7CAAAewgFu0HU+AAAAgUlEQVQ4jdXSwQnAIAxA0QxQcIHSrOpojuIIHj2IqR7zU3rXm4/wUVTk9HUTUoBMqABtnBiESTBU1QonGmEQUFVDNRmqCxrBV1djcsJXNxSCq66GdU4EqL/R3eA5wsE6wV9OP64vgEnwzdUIz1AIGcDHVjQlhQ9TCGjKg71chBPXC+guVzpvSA/2AAAAAElFTkSuQmCC",
        "play_circle": "iVBORw0KGgoAAAANSUhEUgAAAIAAAABAAQMAAADoGO08AAAABlBMVEUAAAD///+l2Z/dAAAACXBIWXMAAB7CAAAewgFu0HU+AAAA9ElEQVQ4jbWTMQ7DIAxFbWVgzNgxvUF7gtIjdewQNRyNozB2zJAhQ1RqEkpsM3SKpUTi6dsY/AE4MLq3XOMQJTAxBpkR4yyAnS4fAeIdRRFcAAbHa1KBllc1tDAjA62nNA46yke+7y39egZe5ZejL7Ica3qnQcsaHeFMYG8VAzypMwF6AZoAloDfgU9nbSQISfcLEtsRUCoWoXBAY0CZEh0qhdcg/E3hu2zbqpRZK4I+i+cAq+PrC6I7fWhwFZcM65zZGOpBVaOshm2LLEdXCuVIlmq4pUzYvh1oWybjWtYoWdtJa9fmr55H9YAwqicGpwkOjC8IWW9N6FgJuAAAAABJRU5ErkJggg==",
        "power": "iVBORw0KGgoAAAANSUhEUgAAAIAAAABAAQMAAADoGO08AAAABlBMVEUAAAD///+l2Z/dAAAACXBIWXMAAB7CAAAewgFu0HU+AAAAsklEQVQ4jc3RQQrDIBAFUCWLWXoEb1IvFqxH8yhzBJcupFOni/CnEEug0EoQfCTfCd+5n66tvgHx96EQezz7SrwVnIKJCSehRhwwJSg0BM1AiAodQa9FSDrYWEFWyCvYFW4rGArpEnSFuILPn7x+I12CXTccPR/bGaQj6Aximf2aGursF0F7JWxOD6Zsmq9HhO3h3L0CeCnzAXDSguDZJZFhIIp0AyTCBrzYzBliI/5wPQFov1oTW3AKDgAAAABJRU5ErkJggg==",
        "volume": "iVBORw0KGgoAAAANSUhEUgAAAIAAAABAAQMAAADoGO08AAAABlBMVEUAAAD///+l2Z/dAAAACXBIWXMAAB7CAAAewgFu0HU+AAAAw0lEQVQ4jcWTvQ0DIQyFD1FQMgKjsFkwUiQ2Shk5FWswwpVXnOKQjmeXkS50fDLPf49t++8hdXeVFXjtCEI9NXgjSFVQNpOgauE0AAhFSOOE/LECL+Qgb5iSAOJMeoMyJshQhrQVuIdIp7TmEGkjEYI9GsAA+hFUxBkwoh0a6Ihunljgx88apg5detfNtaHbB/CcgJcRfofccepJ7rgXs6igd+uFERg7GMNshfIAkLkwAGPLWAXu1tpem99VlLAf6OLzAfmrobheyJl4AAAAAElFTkSuQmCC",
    }
    for img in logo:
        logo[img] = Image.open(io.BytesIO(base64.b64decode(logo[img]))).convert(device.mode)
    return logo


def get_config(file):
    base_path = os.path.abspath(os.path.dirname(__file__))
    font_path = os.path.join(base_path, "fonts",
                             "Bitstream Vera Sans Mono Roman.ttf")  # Tried Inconsolata and VT323, but this one looked better
    config = configparser.ConfigParser()
    config.read(os.path.join(base_path, file))
    config_dict = {"PATH": {}, "FONT": {}}

    for section in config.sections():
        config_dict[section] = {}
        for key in config.options(section):
            config_dict[section][key] = config.get(section, key)

    config_dict["PATH"]["base_path"] = base_path
    config_dict["PATH"]["images"] = os.path.join(base_path, "images")
    config_dict["FONT"]["standard"] = ImageFont.truetype(font_path, 12)
    config_dict["FONT"]["small"] = ImageFont.truetype(font_path, 10)
    config_dict["DISPLAY"]["refresh"] = int(config_dict["DISPLAY"]["refresh"])

    for key in config_dict["LEDS"]:
        config_dict["LEDS"][key] = int(config_dict["LEDS"][key])

    return config_dict


def get_device(deviceName):
    actual_args = ["-d", deviceName]
    parser = cmdline.create_parser(description="luma.examples arguments")
    args = parser.parse_args(actual_args)
    if args.config:
        config = cmdline.load_config(args.config)
        args = parser.parse_args(config + actual_args)
    try:
        device = cmdline.create_device(args)
    except error.Error as e:
        parser.error(e)
    return device


def get_wifi():
    wififile = "/proc/net/wireless"

    if not os.path.exists(wififile):
        return "--"

    wifirateFile = open(wififile)
    wifiline = wifirateFile.readlines()[2]  # last line
    wifirateFile.close()
    return int(math.ceil(float(re.split(r"\s+", wifiline)[3])))


def sigterm_handler(*_):
    disable_leds()
    draw_logo("power")
    sys.exit(0)


def draw_logo(image_name):
    device.display(logo[image_name])
    sleep(config["DISPLAY"]["refresh"])


def time_convert(s):
    result = re.search(r"^\d+:([^.]+)\.*", str(timedelta(seconds=float(s))))
    return result.groups()[0]


def mpd_state_convert(s):
    state = {
        "play": MpdStatus.PLAY,
        "pause": MpdStatus.PAUSE,
        "stop": MpdStatus.STOP,
    }
    return state[s]


def mpd_file_convert(s):
    name = {
        #
        "artist": "",
        "title": "",
        "album": "",
    }

    result = re.search(r"^(.+)/([^/]+)\.[^.]+$", s)  # Kinderlieder/Kinderlieder Klassiker/1/Track.02.mp3
    if not result or result.groups()[0].startswith("http"):
        return name
    name["artist"] = result.groups()[0]
    name["title"] = result.groups()[1]
    return name


def mpd_get_data(key, data, altdata):
    if key in data:
        return data[key]

    if key in altdata:
        return altdata[key]

    return ""


def mpd_get_alt_data(data):
    alt_data = {
        "song": -1,
        "playlistlength": 0,
        "elapsed": 0,
        "duration": 1,  # cant be zero (division). also 0 would mean 100%. with 1, its 0%
        "file": "/dev/null",
        "artist": "",
        "title": "",
        "album": "",
    }

    if "file" in data:
        alt_data["file"] = data["file"]
        alt_data.update(mpd_file_convert(data["file"]))

    return alt_data


def mpd_get_track_num_current(key, data, alt_data):
    return int(mpd_get_data(key, data, alt_data)) + 1


def mpd_get_track_num_total(key, data, alt_data):
    return int(mpd_get_data(key, data, alt_data))


def mpd_get_track_time(key, data, alt_data):
    return time_convert(mpd_get_data(key, data, alt_data))


def mpd_get_track_time_percent(data, alt_data):
    current_seconds = float(mpd_get_data("elapsed", data, alt_data))
    total_seconds = float(mpd_get_data("duration", data, alt_data))
    percent = 100 / total_seconds * current_seconds
    return percent


def mpd_client():
    # Wir versuchen zu pingen, um zu sehen, ob die Verbindung noch steht
    try:
        mpdc.ping()
    except (mpd.ConnectionError, BrokenPipeError):
        try:
            mpdc.connect(config["MPD"]["host"], int(config["MPD"]["port"]))
        except Exception as e:
            print(f"Verbindungsfehler: {e}")
            return None  # Falls MPD gar nicht erreichbar ist

    # {'volume': '30', 'repeat': '0', 'random': '0', 'single': '0', 'consume': '0', 'partition': 'default', 'playlist': '12', 'playlistlength': '5', 'mixrampdb': '0.000000', 'state': 'play', 'song': '0', 'songid': '56',
    # 'time': '26:79', 'elapsed': '26.377', 'bitrate': '320', 'duration': '78.968', 'audio': '44100:24:2', 'nextsong': '1', 'nextsongid': '57'}
    # of those, volume, playlistlength, state (play, pause, stop), song (currently playing song in list, starts with 0), elapsed and duration are of interest.
    status = mpdc.status()
    # {'file': 'Kinderlieder/Kinderlieder Klassiker/1/Track.05.mp3', 'last-modified': '2021-11-07T09:51:56Z', 'time': '87', 'duration': '87.222', 'pos': '4', 'id': '60'}
    # {'file': 'Musik/2008 For Emma, Forever Ago (L)/01. Flume.mp3', 'last-modified': '2013-07-02T12:56:55Z', 'time': '219', 'duration': '219.062', 'pos': '0', 'id': '61',
    # 'artist': 'Bon Iver', 'title': 'Flume', 'album': 'For Emma, Forever Ago', 'track': '1', 'date': '2008', 'genre': 'Folk-rock, Indie folk'}
    # first row is always present. all in all file, artist, title, album are of interest.
    song = mpdc.currentsong()
#    mpdc.close()
#    mpdc.disconnect()

    alt_data = mpd_get_alt_data(song)
    return {
        "status": mpd_state_convert(status["state"]),
        "volume": status["volume"],
        "track_num_current": mpd_get_track_num_current("song", status, alt_data),
        "track_num_total": mpd_get_track_num_total("playlistlength", status, alt_data),
        "track_time_elapsed": mpd_get_track_time("elapsed", status, alt_data),
        "track_time_total": mpd_get_track_time("duration", status, alt_data),
        "track_time_percent": mpd_get_track_time_percent(status, alt_data),
        "file_path": mpd_get_data("file", song, alt_data),
        "artist": mpd_get_data("artist", song, alt_data),
        "title": mpd_get_data("title", song, alt_data),
        "album": mpd_get_data("album", song, alt_data),
    }


class TextImage:
    def __init__(self, text, font):
        draw = ImageDraw.Draw(Image.new(device.mode, (device.width, device.height)))
        self.left, self.top, self.right, self.bottom = draw.textbbox((0, 0), text, font=font)
        self.image = Image.new(device.mode, (self.right, self.bottom))
        draw = ImageDraw.Draw(self.image)
        draw.text((0, 0), text, font=font, fill="white")
        self.width = self.right
        self.height = self.bottom
        del draw


def compose_text(text, cords):
    return ComposableImage(TextImage(text, cords[2]).image, position=(cords[0], cords[1]))


def get_coordinates():
    font_std = config["FONT"]["standard"]
    font_small = config["FONT"]["small"]
    cords = {
        # horizontal dividers. 64 pixels (0-63) divided in 4 sections a 16 pixels
        "section0_y": 0,  # start
        "section1_y": 15,  # TITLE
        "section2_y": 31,  # ARTIST
        "section3_y": 47,  # ALBUM
        "section4_y": 63,  # STATUS. no need to draw
        # vertical dividers for status section. 128 pixels (0-127) divided in 4 sections. The first two need 5 chars, the other two 4 chars.
        # this makes 36 pixels for the left and 28 for the right side
        "section4_x0": 0,  # TIME START
        "section4_x1": 35,  # TIME
        "section4_x2": 71,  # TRACK
        "section4_x3": 99,  # VOLUME
        "section4_x4": 127,  # WIFI. no need to draw
        "scroll": 10,  # pixel advancement per tick
    }

    cords["title"] = [0, cords["section0_y"] + 1, font_std]
    cords["artist"] = [0, cords["section1_y"] + 1, font_std]
    cords["album"] = [0, cords["section2_y"] + 1, font_std]
    cords["track_time_elapsed"] = [cords["section4_x0"], cords["section3_y"] + 2, font_small]
    cords["track"] = [cords["section4_x1"] + 2, cords["section3_y"] + 1, font_small]
    cords["volume"] = [cords["section4_x2"] + 2, cords["section3_y"] + 1, font_small]
    cords["wifi"] = [cords["section4_x3"] + 2, cords["section3_y"] + 1, font_small]
    cords["progress1_start"] = [cords["section4_x0"], cords["section4_y"]]
    cords["progress2_start"] = [cords["section4_x0"], cords["section4_y"] - 1]
    return cords


def get_outlines(cords):
    return [
        # horizontal dividers
        # [0, cords["section1_y"], device.width, cords["section1_y"]],  # x,y to x,y
        # [0, cords["section2_y"], device.width, cords["section2_y"]],
        [0, cords["section3_y"], device.width, cords["section3_y"]],
        # vertical dividers
        [cords["section4_x1"], cords["section3_y"], cords["section4_x1"], device.height],
        [cords["section4_x2"], cords["section3_y"], cords["section4_x2"], device.height],
        [cords["section4_x3"], cords["section3_y"], cords["section4_x3"], device.height],
    ]


def get_scroll_count(image_width, screen_width, scroll_tick):
    if image_width <= screen_width:
        return 0
    offscreen = image_width - screen_width
    return math.ceil(offscreen / scroll_tick)


def add_image(current, coordinates, image_composition, key, text):
    image = compose_text(text, coordinates[key])
    current[key] = {
        #
        "text": text,
        "image": image,
    }
    image_composition.add_image(image)
    current[key]["max_scroll"] = get_scroll_count(image.width, device.width, coordinates["scroll"])
    current[key]["cur_scroll"] = 0


def update_images(current, image_composition, coordinates, new):
    # if there is a content update, remove the old image, render and add the new content
    for key in new:
        if not key in coordinates:
            continue
        if not key in current:  # first iteration
            add_image(current, coordinates, image_composition, key, new[key])

        if current[key]["text"] != new[key]:  # updated content
            image_composition.remove_image(current[key]["image"])
            add_image(current, coordinates, image_composition, key, new[key])
            continue

        if current[key]["max_scroll"] != 0:  # scrolling
            if current[key]["cur_scroll"] == current[key]["max_scroll"]:
                # reset image
                current[key]["image"].offset = (0, 0)
                current[key]["cur_scroll"] = 0
                continue

            # scroll image
            current[key]["image"].offset = (current[key]["image"].offset[0] + coordinates["scroll"], 0)
            current[key]["cur_scroll"] += 1

    return current


def update_counter(max_count, count):
    if count == max_count:
        return 0, 1
    count += 1
    return count, 0


def update_state(state):
    try:
        mpc = mpd_client()
        if mpc is None:
            return state
    except:
        return state

    # the if statements here indicate distinct events, where actions could be added
    if mpc["status"] != state["status"]:
        state["wifi"] = get_wifi()  # a state change might be a good time to update wifi signal
        state["status"] = mpc["status"]

    if mpc["volume"] != state["volume"]:
        state["volume"] = mpc["volume"]

    artists: str = ",".join(mpc["artist"]) if isinstance(mpc["artist"], (list, tuple)) else mpc["artist"]
    current_id = artists + mpc["title"] + str(mpc["track_num_current"]) + mpc["track_time_total"]

    if current_id != state["id"]:  # track change
        state["id"] = current_id
        state["album"] = mpc["album"]
        state["title"] = mpc["title"]
        state["artist"] = artists

    # below are non-events
    if mpc["file_path"].startswith(
            "http"):  # what is in track_time_percent or others when there is a stream running? i doubt this file check is good
        state["progress"] = device.width
    else:
        state["progress"] = int(math.ceil(device.width * mpc["track_time_percent"] / 100))

    state["track_time_elapsed"] = mpc["track_time_elapsed"]
    state["track_num_current"] = mpc["track_num_current"]
    state["track_num_total"] = mpc["track_num_total"]

    return state


def pad_state(state):
    if "volume" in state:
        padding = " "
        if state["volume"] == 100:
            padding = ""
        state["volume"] = "V" + padding + str(state["volume"])

    if state["status"] == MpdStatus.PAUSE:
        state["track_time_elapsed"] = "PAUSE"
    else:
        if len(state["track_time_elapsed"]) == 4:
            state["track_time_elapsed"] = " " + state["track_time_elapsed"]

    if "track_num_current" in state and "track_num_total" in state:
        track_cur = str(state["track_num_current"])
        track_total = str(state["track_num_total"])
        if len(track_cur) == 1:
            track_cur = "0" + track_cur
        if len(track_total) == 1:
            track_total = "0" + track_total
        state["track"] = track_cur + "/" + track_total

    if "wifi" in state:
        wifi = str(state["wifi"])
        padding = " "
        if len(wifi) == 3:
            padding = ""
        state["wifi"] = "W" + padding + wifi

    return state


def sleep_configured_refresh_time():
    sleep(config["DISPLAY"]["refresh"])


def draw_logos_on_status_change(old_state, current_state):
    if old_state["status"] != current_state["status"]:
        if current_state["status"] == MpdStatus.PLAY:
            draw_logo("play")
            return True
        elif current_state["status"] == MpdStatus.PAUSE:
            draw_logo("pause")
            return True
        elif current_state["status"] == MpdStatus.STOP:
            draw_logo("card")
            return True

    if parse_volume(current_state["volume"]) > parse_volume(old_state["volume"]):
        draw_logo("volume")
        return True
    if parse_volume(current_state["volume"]) < parse_volume(old_state["volume"]):
        draw_logo("volume")
        return True

    return False


def parse_volume(volume) -> int:
    if type(volume) is str:
        return int(volume[1:]) if volume.startswith("V") else int(volume)
    if type(volume) is int:
        return volume
    return 0


def main():
    image_composition = ImageComposition(device)
    coordinates = get_coordinates()
    current_display = {}
    current_state = {
        #
        "status": MpdStatus.STOP,
        "volume": 0,
        "track_num_current": 0,
        "track_num_total": 0,
        "track_time_elapsed": "00:00",
        "track_time_total": "00:00",
        "track_time_percent": 0,
        "file_path": "",
        "artist": "",
        "title": "",
        "album": "",
        "progress": 0,
        "id": ".",
        "count": 0,
    }

    try:
        while True:
            old_state = current_state.copy()
            current_state = update_state(current_state)
            status_change_detected: bool = draw_logos_on_status_change(old_state, current_state)

            if current_state["status"] == MpdStatus.STOP and not status_change_detected:
                draw_logo("card")
                sleep_configured_refresh_time()  # take a nap. continue would skip that otherwise.
                continue

            current_display = update_images(current_display, image_composition, coordinates,
                                            pad_state(current_state.copy()))

            with canvas(device, background=image_composition()) as draw:
                image_composition.refresh()
                for line in get_outlines(coordinates):
                    draw.line(line[0:4], fill="white")
                # progress bar
                draw.line(
                    (coordinates["progress1_start"][0], coordinates["progress1_start"][1], current_state["progress"],
                     coordinates["progress1_start"][1]),
                    fill="white",
                )
                draw.line(
                    (coordinates["progress2_start"][0], coordinates["progress2_start"][1], current_state["progress"],
                     coordinates["progress2_start"][1]),
                    fill="white",
                )
            sleep(config["DISPLAY"]["refresh"])
    except KeyboardInterrupt:
        pass

    return


if __name__ == "__main__":
    config = get_config("oled_phoniebox.conf")
    enable_leds()
    device = get_device(config["DISPLAY"]["controller"])
    device.contrast(int(config["DISPLAY"]["contrast"]))
    logo = get_logo()
    mpdc = MPDClient()
    signal.signal(signal.SIGTERM, sigterm_handler)
    draw_logo("music_note")
    main()
    disable_leds()
