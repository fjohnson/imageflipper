import threading
import logging

from SearchTermServer import SearchTermServer


class ImageDownloader(threading.Thread):
    def __init__(self, image_set, image_download_interval, search_term_download, server):
        super(self.__class__, self).__init__()
        self.daemon = True
        self.display_images = False
        self.logger = logging.getLogger('main_logger')
        self.image_set = image_set
        self.image_download_interval = image_download_interval
        self.search_term_download = search_term_download
        self.server = server

    def run(self):

        while True:
            self.search_term_download()
            self.server.new_term_event.wait(self.image_download_interval)
            self.logger.info('image downloader woke up')