import logging
import os
import pprint
import shutil
import threading

from socketserver import ThreadingTCPServer, StreamRequestHandler
from ImageCleaner import ImageCleaner
from config import vars, TYPE_RESOLUTION


class SearchTermServer(ThreadingTCPServer):
    def __init__(self, image_dir, image_set, image_lock, max_file_age, refresh_event, daemon=True):

        super().__init__(('localhost', 9999), TCPHandler, bind_and_activate=True)
        self.image_directory = image_dir
        self.max_file_age = max_file_age
        self.logger = logging.getLogger("main_logger")
        self.new_term_event = threading.Event()
        self.images = image_set
        self.image_lock = image_lock
        self.refresh_event = refresh_event
        self.clean_event = threading.Event()
        self.clean_result_event = threading.Event()
        self.clean_msg_buffer = []
        self.image_clean_interval = 60*60*24
        self.image_cleaner = ImageCleaner(image_dir, image_lock, image_set, max_file_age, self.image_clean_interval,
                                          self.clean_event, self.clean_result_event, self.clean_msg_buffer, self.refresh_event)
        self.image_cleaner.start()

        self.welcome_msg = '''Hello. Type ^commands for a list of commands'''

        self.commands = {"^exit": "Exit.",
                         "^vars": "Modify runtime parameters. Syntax is: ^vars key:value key:value...",
                         "^space": "Show device disk space",
                         "^clear": "Force an image clean event",
                         "^idea": "Show how much space is taken up my images",
                         "^term": "Show search terms",
                         "^download": "Trigger a download event",
                         "Add/remove vars":"Syntax[-]term,...,[-]term."
                         }

    def check_space(self):
        return shutil.disk_usage("/")

    def image_space_taken(self):
        total_size = 0
        megs = 1024*1024.0
        gigs = megs*1024

        for search_term in os.listdir(self.image_directory):
            search_term_img_dir = os.path.join(self.image_directory, search_term)
            if not os.path.isdir(search_term_img_dir):
                continue
            for img_file in os.listdir(search_term_img_dir):
                file_path = os.path.join(search_term_img_dir, img_file)
                file_size = os.stat(file_path).st_size
                total_size += file_size

        return total_size / megs, total_size / gigs

    def format_delete_report(self, report):
        items = []
        days = 60*60*24
        for item in sorted(report, key=lambda i: i.filename):
            items.append("{}, mtime (days):{:.2f}, space:{:.2f}kb".format(item.filename, item.age/days, item.space/1024))
        return '\r\n'.join(items)


    def clear_oldies(self):
        self.clean_event.set()
        self.clean_result_event.wait()
        self.clean_result_event.clear()

        if self.clean_msg_buffer:
            return self.format_delete_report(self.clean_msg_buffer.pop())

    def add_extra_images(self, data):
        tokens = data.split(",")
        extra_imgs = set(vars['extra_images'])
        to_remove = set()
        to_add = set()

        for t in tokens:
            t = t.strip()
            try:
                imgs = os.listdir(os.path.join(self.image_directory, t))
            except FileNotFoundError:
                continue

            if t.startswith('-'):
                t = t[1:]
                try:
                    extra_imgs.remove(t)
                except KeyError:
                    continue
                to_remove.update(imgs)
            else:
                extra_imgs.add(t)
                to_add.update(imgs)

        self.image_lock.acquire()
        for i in self.images & to_remove:
            self.images.remove(i)
        self.images.update(to_add)
        self.image_lock.release()
        vars['extra_imgs'] = extra_imgs
        self.refresh_event.set()

        return extra_imgs
class TCPHandler(StreamRequestHandler):

    def send_response(self, str):
        self.wfile.write(bytes("{}\n".format(str),'utf8'))

    def list_vars(self):
        return pprint.pformat(vars)

    def modify_vars(self, var_string):
        keypairs_str = var_string.partition("^vars ")[-1].split(":")
        parsed_vars = {}
        i = 1
        while i < len(keypairs_str):
            k, v = keypairs_str[i - 1], keypairs_str[i]
            parsed_vars[k] = TYPE_RESOLUTION.get(k,str)(v)
            i = i + 1
        vars.update(parsed_vars)
        return self.list_vars()

    def parse_response(self):
        while self.data != "^exit":

            if self.data.startswith("^vars"):
                self.send_response(self.modify_vars(self.data))
            elif self.data.startswith("^lvars"):
                self.send_response(self.list_vars())
            elif self.data == "^space":
                total, used, free = self.server.check_space()
                self.send_response("Total {} Used {} Free {}".format(total, used, free))
            elif self.data == "^clear":
                self.wfile.write(b"Wait...")
                self.send_response(self.server.clear_oldies())
            elif self.data == "^idea":
                self.wfile.write(b"Calculating... ")
                megs, gigs = self.server.image_space_taken()
                self.send_response("Space used: {:.2f}G {:.2f}M".format(gigs, megs))
            elif self.data == "^term":
                self.send_response(vars['search_terms'])
            elif self.data == "^extra":
                self.send_response(pprint.pformat(self.server.add_extra_images()))
            elif self.data == "^download":
                # trigger a download event
                self.server.new_term_event.set()
            elif self.data =="^commands":
                self.send_response(pprint.pformat(self.server.commands))
            else:
                terms_copy = set(vars['search_terms'])
                added_or_removed = False
                user_terms = map(str.strip, self.data.split(','))

                for term in user_terms:
                    if term.startswith("-"):
                        try:
                            terms_copy.remove(term[1:])
                            added_or_removed = True
                        except KeyError:
                            pass
                    else:
                        terms_copy.add(term)
                        added_or_removed = True

                if added_or_removed == True:
                    vars['search_terms'] = terms_copy
                    self.server.new_term_event.set()
                    self.send_response(terms_copy)

            self.wfile.write(bytes(":", 'utf-8'))
            self.data = self.rfile.readline().strip().decode('utf-8')

    def handle(self):
        self.server.logger.info("{} connected".format(self.client_address))
        self.send_response(self.server.welcome_msg)
        self.send_response("Search terms: {}".format(vars['search_terms']))
        self.wfile.write(b"\n:")

        self.data = self.rfile.readline().strip().decode('utf-8')
        self.parse_response()
        self.send_response("Good bye.")

if __name__ == '__main__':
    CODE_DIR = os.path.dirname(__file__)
    IMAGE_DIR = os.path.join(CODE_DIR, "images")
    image_set = set()
    image_lock = threading.Lock()
    MAX_FILE_AGE = 60 * 60 * 24 * 90
    SearchTermServer(IMAGE_DIR, image_set, image_lock, MAX_FILE_AGE).serve_forever()