import socketserver
import threading
import os
import time
import shutil
import logging

class SearchTermServer(threading.Thread):

    search_terms = set()
    image_directory = None
    images_being_displayed = None
    image_lock = None
    logger = None
    new_term_event = threading.Event()

    def __init__(self, image_dir, display_image_set, image_lock, daemon=True, search_terms=None):
        super(self.__class__, self).__init__()
        self.daemon = daemon
        self.host = "localhost"
        self.port = 9999

        SearchTermServer.logger = logging.getLogger("main_logger")

        if search_terms is None:
            SearchTermServer.search_terms = {}
        else:
            SearchTermServer.search_terms = search_terms

        SearchTermServer.image_directory = image_dir
        SearchTermServer.images_being_displayed = display_image_set
        SearchTermServer.image_lock = image_lock

    def run(self):
        server = socketserver.TCPServer((self.host, self.port), SearchTermServer.TCPHandler)
        server.serve_forever()

    @staticmethod
    def check_space():
        return shutil.disk_usage("/")


    @staticmethod
    def clear_oldies():

        days_30 = 60*60*24*30
        current_time = time.time()

        for img_file in list(SearchTermServer.images_being_displayed):
            if current_time - os.stat(img_file).st_mtime >= days_30:
                os.unlink(img_file)
                SearchTermServer.image_lock.acquire()
                SearchTermServer.images_being_displayed.remove(img_file)
                SearchTermServer.image_lock.release()

    @staticmethod
    def image_space_taken():
        total_size = 0
        megs = 1024*1024.0
        gigs = megs*1024

        for search_term in os.listdir(SearchTermServer.image_directory):
            search_term_img_dir = os.path.join(SearchTermServer.image_directory, search_term)
            if not os.path.isdir(search_term_img_dir):
                continue
            for img_file in os.listdir(search_term_img_dir):
                file_path = os.path.join(search_term_img_dir, img_file)
                file_size = os.stat(file_path).st_size
                total_size += file_size

        return total_size / megs, total_size / gigs

    class TCPHandler(socketserver.StreamRequestHandler):

        def setup(self):
            socketserver.StreamRequestHandler.setup(self)
            self.welcome_msg = b'''
Add new search terms by entering in a term then a new line or a comma seperated list followed by a new line. Remove search terms by prefixing with a "-". Send ^exit to exit. \r\n
Type "^space" to determine device space left. Type ^term to list search terms. Type "^clear" to erase images older than 30 days. Type "^idea" to return image directory magnitude.\r\n\n'''

        def handle(self):
            SearchTermServer.logger.info("{} connected".format(self.client_address))
            self.wfile.write(self.welcome_msg)
            self.wfile.write(bytes("Search terms: {}\r\n:".format(SearchTermServer.search_terms), 'utf-8'))

            terms_copy = set(SearchTermServer.search_terms)
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
                        try:
                            total, used, free = SearchTermServer.check_space()
                            ss_str = "Total {} Used {} Free {}\r\n".format(total, used, free)
                            self.wfile.write(ss_str.encode('utf-8'))
                        except IOError as e:
                            self.wfile.write(bytes(" ERROR: {}\r\n".format(e), 'utf-8'))
                            SearchTermServer.logger.info(" ERROR: {}\r\n".format(e))
                    elif term == "^clear":
                        self.wfile.write(b"Wait...")
                        try:
                            SearchTermServer.clear_oldies()
                            self.wfile.write(b" Ok Done *_*.\r\n")
                        except IOError as e:
                            self.wfile.write(bytes(" ERROR: {}\r\n".format(e), 'utf-8'))
                            SearchTermServer.logger.info(" ERROR: {}\r\n".format(e))
                    elif term == "^idea":
                        self.wfile.write(b"Calculating... ")
                        try:
                            megs, gigs = SearchTermServer.image_space_taken()
                            self.wfile.write(bytes("Space used: {}G {}M\r\n".format(gigs, megs), 'utf-8'))
                        except IOError as e:
                            self.wfile.write(bytes(" ERROR: {}\r\n".format(e), 'utf-8'))
                            SearchTermServer.logger.info(" ERROR: {}\r\n".format(e))
                    elif term == "^term":
                        self.wfile.write(bytes("{}\r\n".format(SearchTermServer.search_terms), 'utf-8'))
                    elif term:
                        terms_copy.add(term)
                        added_or_removed = True

                if added_or_removed == True:
                    SearchTermServer.search_terms = terms_copy
                    SearchTermServer.new_term_event.set()
                    self.wfile.write(bytes("{}\r\n".format(SearchTermServer.search_terms), 'utf-8'))

                added_or_removed = False
                self.wfile.write(bytes(":", 'utf-8'))
                self.data = self.rfile.readline().strip().decode('utf-8')

            self.wfile.write(b"Good bye.\r\n")

if __name__ == '__main__':
    imgdir = 'C:\\Users\\fjohnson\\Desktop\\imageflipper-master\\images'
    display_img_set = set()
    lock_event = threading.Event()
    SearchTermServer(imgdir, display_img_set, lock_event, daemon=False).start()