import SocketServer
import threading
import os
import time

class SearchTermServer(threading.Thread):

    search_terms = set()
    image_directory = None
    images_being_displayed = None
    image_event_lock = None

    def __init__(self, image_dir, display_image_set, image_lock, daemon=True, search_terms=None):
        super(self.__class__, self).__init__()
        self.daemon = daemon
        self.host = "localhost"
        self.port = 9999
        if search_terms is None:
            SearchTermServer.search_terms = {}
        else:
            SearchTermServer.search_terms = search_terms

        SearchTermServer.image_directory = image_dir
        SearchTermServer.images_being_displayed = display_image_set
        SearchTermServer.image_event_lock = image_lock

    def run(self):
        server = SocketServer.TCPServer((self.host, self.port), SearchTermServer.TCPHandler)
        server.serve_forever()

    @staticmethod
    def check_space():
        result = os.statvfs('/')
        block_size = result.f_frsize
        blocks_available = result.f_bavail
        return blocks_available*block_size / 1024.0**3

    @staticmethod
    def clear_oldies():
        SearchTermServer.image_event_lock.set()
        days_30 = 60*60*24*30
        current_time = time.time()

        for img_file in list(SearchTermServer.images_being_displayed):
            if current_time - os.stat(img_file).st_mtime >= days_30:
                os.unlink(img_file)
                SearchTermServer.images_being_displayed.remove(img_file)
        SearchTermServer.image_event_lock.clear()

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

    class TCPHandler(SocketServer.StreamRequestHandler):

        def setup(self):
            SocketServer.StreamRequestHandler.setup(self)
            self.EOT = "\x04"
            self.welcome_msg = '''
    Add new search terms by entering in a term then a new line or a comma seperated list followed by a new line. Remove search terms by prefixing with a "-". Send an EOF to exit.
    Type "^space" to determine device space left. Type "^clear" to erase images older than 30 days. Type "^idea" to return image directory magnitude.
    '''

        def handle(self):
            self.wfile.write(self.welcome_msg)
            self.wfile.write("Search terms: {}\n:".format(SearchTermServer.search_terms))

            terms_copy = set(SearchTermServer.search_terms)
            self.data = self.rfile.readline().strip()

            while self.data != self.EOT:
                user_terms = map(str.strip, self.data.split(','))
                for term in user_terms:
                    if term.startswith("-"):
                        try:
                            terms_copy.remove(term[1:])
                        except KeyError:
                            pass
                    elif term == "^space":
                        try:
                            self.wfile.write("Space available: {}G\n".format(SearchTermServer.check_space()))
                        except IOError as e:
                            self.wfile.write(" ERROR: {}\n".format(e))
                    elif term == "^clear":
                        self.wfile.write("Wait...")
                        try:
                            SearchTermServer.clear_oldies()
                            self.wfile.write(" Ok Done *_*.\n")
                        except IOError as e:
                            self.wfile.write(" ERROR: {}\n".format(e))

                    elif term == "^idea":
                        self.wfile.write("Calculating... ")
                        try:
                            megs, gigs = SearchTermServer.image_space_taken()
                            self.wfile.write("Space used: {}G {}M\n".format(gigs, megs))
                        except IOError as e:
                            self.wfile.write(" ERROR: {}\n".format(e))
                    elif term:
                        terms_copy.add(term)
                self.wfile.write(self.data)
                self.wfile.write("Search terms: {}\n:".format(terms_copy))
                self.data = self.rfile.readline().strip()

            SearchTermServer.search_terms = terms_copy

            self.wfile.write("Updated search terms: {}\n".format(SearchTermServer.search_terms))
            self.wfile.write("Good bye.\n")

# if __name__ == '__main__':
#     SearchTermServer(daemon=False).start()