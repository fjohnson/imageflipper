import logging
import os
import pprint
import shutil
import threading

from socketserver import ThreadingTCPServer, StreamRequestHandler
from ImageCleaner import ImageCleaner

class SearchTermServer(ThreadingTCPServer):
    def __init__(self, image_dir, image_set, image_lock, max_file_age, daemon=True, search_terms=None):

        super().__init__(('localhost', 9999), TCPHandler, bind_and_activate=True)
        self.image_directory = image_dir
        self.max_file_age = max_file_age
        self.search_terms = search_terms if search_terms else set()
        self.logger = logging.getLogger("main_logger")
        self.new_term_event = threading.Event()

        self.clean_event = threading.Event()
        self.clean_result_event = threading.Event()
        self.clean_msg_buffer = []
        self.image_clean_interval = 60*60*24
        self.image_cleaner = ImageCleaner(image_dir, image_lock, image_set, max_file_age, self.image_clean_interval, self.clean_event, self.clean_result_event, self.clean_msg_buffer)
        self.image_cleaner.start()

        self.welcome_msg = '''
Add new search terms by entering in a term then a new line or a comma seperated list followed by a new line. Remove search terms by prefixing with a "-". Send ^exit to exit. \r\n
Type "^space" to determine device space left. Type ^term to list search terms. Type "^clear" to erase images older than {} seconds. Type "^idea" to return image directory magnitude.'''.format(self.max_file_age)

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

class TCPHandler(StreamRequestHandler):

    def send_response(self, str):
        self.wfile.write(bytes("{}\r\n".format(str),'utf8'))

    def handle(self):
        self.server.logger.info("{} connected".format(self.client_address))
        self.send_response(self.server.welcome_msg)
        self.send_response("Search terms: {}".format(self.server.search_terms))
        self.wfile.write(b"\r\n:")

        terms_copy = set(self.server.search_terms)
        self.data = self.rfile.readline().strip().decode('utf-8')

        added_or_removed = False
        while self.data != "^exit":
            user_terms = map(str.strip, self.data.split(','))

            for term in user_terms:
                if term.startswith("-"):
                    try:
                        terms_copy.remove(term[1:])
                        added_or_removed = True
                    except KeyError:
                        pass
                elif term == "^space":
                    total, used, free = self.server.check_space()
                    self.send_response("Total {} Used {} Free {}".format(total, used, free))
                elif term == "^clear":
                    self.wfile.write(b"Wait...")
                    self.send_response(self.server.clear_oldies())
                elif term == "^idea":
                    self.wfile.write(b"Calculating... ")
                    megs, gigs = self.server.image_space_taken()
                    self.send_response("Space used: {}G {}M".format(gigs, megs))
                elif term == "^term":
                    self.send_response(self.server.search_terms)
                elif term:
                    terms_copy.add(term)
                    added_or_removed = True

            if added_or_removed == True:
                self.server.search_terms = terms_copy
                self.server.new_term_event.set()
                self.send_response(self.server.search_terms)

            added_or_removed = False
            self.wfile.write(bytes(":", 'utf-8'))
            self.data = self.rfile.readline().strip().decode('utf-8')

        self.wfile.write(b"Good bye.\r\n")

if __name__ == '__main__':
    CODE_DIR = os.path.dirname(__file__)
    IMAGE_DIR = os.path.join(CODE_DIR, "images")
    image_set = set()
    image_lock = threading.Lock()
    MAX_FILE_AGE = 60 * 60 * 24 * 90
    SearchTermServer(IMAGE_DIR, image_set, image_lock, MAX_FILE_AGE).serve_forever()