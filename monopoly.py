import logging
import time
import signal
import hashlib
import json

from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.utils.crypto import constant_time_compare

from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
from tornado.options import define, parse_command_line, options
from tornado.web import Application, HTTPError, RequestHandler
from tornado.websocket import WebSocketHandler

from collections import defaultdict

define('debug', default=True, type=bool, help='Run in debug mode')
define('port', default=8080, type=int, help='Server port')
define('allowed_hosts', default="localhost:8080", multiple=True, help='Allowed hosts for cross domain connections')

class PlayerHandler(WebSocketHandler):
    def open(self, Game):
        self.Game = Game
        self.application.add_player(self.Game, self)
        print("New connection")

    def on_message(self, message, game= None):
        if game is None:
            game = self.Game
        self.application.broadcast(message, game=game)

    def on_close(self):
        print("Connection closed")

    def check_origin(self, origin):
        return True

class UpdateHandler(RequestHandler):

    def post(self, Game):
        self._broadcast(Game)

    def put(self, Game):
        self._broadcast(Game)

    def _broadcast(self, game):
        try:
            body = json.loads(self.request.body.decode('utf-8'))
        except ValueError:
            body = None
        message = json.dumps(body)
        self.application.broadcast(message, game=game)
        self.write("Ok")

class GameApplication(Application):
    def __init__(self, **kwargs):
        routes = [
            (r'/socket/(?P<Game>[0-9]+)', PlayerHandler),
            (r'/(?P<Game>[0-9]+)', UpdateHandler),
        ]
        super().__init__(routes, **kwargs)
        self.subscriptions = defaultdict(list)

    def add_player(self, game, player):
        for key,value in self.subscriptions.items():
            if player in value:
                self.remove_player(key, player)
        self.subscriptions[game].append(player)

    def remove_player(self, game, player):
        self.subscriptions[game].remove(player)

    def get_players(self, game):
        return self.subscriptions[game]

    def broadcast(self, message, game = None, sender = None):
        if game is not None:
            print(self.get_players(123))
            print(self.get_players(game))
            for peer in self.get_players(game):
                if peer != sender:
                    try:
                        peer.write_message(message)
                    except:
                        self.remove_player(game, peer)

def shutdown(server):
    ioloop = IOLoop.instance()
    logging.info('Stopping server.')
    server.stop()

    def finalize():
        ioloop.stop()
        logging.info('Stopped.')

    ioloop.add_timeout(time.time() + 1.5, finalize)

if __name__ == '__main__':
    parse_command_line()
    app = GameApplication(debug=options.debug)
    server = HTTPServer(app)
    server.listen(options.port)
    signal.signal(signal.SIGINT, lambda sig, frame: shutdown(server))
    logging.info('Listening on port %d', options.port)
    IOLoop.instance().start()    
