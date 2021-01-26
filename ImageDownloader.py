import threading
import logging

from SearchTermServer import SearchTermServer


class ImageDownloader(threading.Thread):
    def __init__(self, image_set, image_download_interval, search_term_download):
        super(self.__class__, self).__init__()
        self.daemon = True
        self.display_images = False
        self.logger = logging.getLogger('main_logger')
        self.image_set = image_set
        self.image_download_interval = image_download_interval
        self.search_term_download = search_term_download

    def run(self):

        while True:
            self.search_term_download()
            if self.image_set:
                self.display_images = True
            else:
                self.display_images = False
                SearchTermServer.new_term_event.wait(self.image_download_interval)
                self.logger.info('image downloader woke up')