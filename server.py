import SocketServer
import threading

class SearchTermServer(threading.Thread):

    search_terms = set()

    def __init__(self, daemon=True, search_terms=None):
        super(self.__class__, self).__init__()
        self.daemon = daemon
        self.host = "localhost"
        self.port = 9999
        if search_terms is None:
            SearchTermServer.search_terms = {}
        else:
            SearchTermServer.search_terms = search_terms

    def run(self):
        server = SocketServer.TCPServer((self.host, self.port), SearchTermServer.TCPHandler)
        server.serve_forever()

    class TCPHandler(SocketServer.StreamRequestHandler):

        def setup(self):
            SocketServer.StreamRequestHandler.setup(self)
            self.EOT = "\x04"
            self.welcome_msg = '''
    Add new search terms by entering in a term then a new line or a comma seperated list followed by a new line. Remove search terms by prefixing with a "-". Send an EOF to exit.
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
                    elif term:
                        terms_copy.add(term)
                self.wfile.write(self.data)
                self.wfile.write("Search terms: {}\n:".format(terms_copy))
                self.data = self.rfile.readline().strip()

            SearchTermServer.search_terms = terms_copy

            self.wfile.write("Updated search terms: {}\n".format(SearchTermServer.search_terms))
            self.wfile.write("Good bye.\n")

if __name__ == '__main__':
    SearchTermServer(daemon=False).start()